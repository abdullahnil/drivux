"""Arka plan servisi: klasörleri rclone bisync ile iki yönlü eşitler.

- Ayarlanan aralıkla düzenli olarak eşitler.
- Klasörde bir değişiklik olunca birkaç saniye bekleyip eşitler.
- USR1 sinyaliyle hemen eşitler, HUP sinyaliyle ayarları yeniden okur.
- Sonuçları durum dosyasına yazar; hata olunca masaüstü bildirimi gösterir.
"""

import os
import signal
import subprocess
import threading
import time

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from . import ortak  # noqa: E402

BEKLEME_SN = 15          # son değişiklikten sonra eşitlemeden önce beklenecek süre
SESSIZ_SN = 5            # eşitlemeden hemen sonra kendi değişikliklerimizi yok say
EN_FAZLA_IZLEME = 3000   # izlenecek en fazla alt klasör


def log(mesaj: str) -> None:
    print(mesaj, flush=True)


def bildir(baslik: str, govde: str) -> None:
    subprocess.run(
        ["notify-send", "-a", "Drive Bağlantı", "-i", ortak.UYGULAMA_KIMLIGI, baslik, govde],
        capture_output=True,
    )


def rclone_hata_ozeti(cikti: str) -> str:
    satirlar = [s for s in cikti.splitlines() if "ERROR" in s or "Failed" in s or "error" in s]
    if not satirlar:
        satirlar = cikti.strip().splitlines()[-3:]
    ozet = satirlar[-1] if satirlar else "Bilinmeyen hata"
    # "2026/11/22 23:43:32 ERROR : " gibi öneki at
    if " : " in ozet:
        ozet = ozet.split(" : ", 1)[1]
    return ozet.strip()[:300]


class Servis:
    def __init__(self):
        self.ayar = ortak.ayar_oku()
        self.durum = ortak.durum_oku()
        self.durum.setdefault("klasorler", {})
        self.kilit = threading.Lock()
        self.izleyiciler: list[Gio.FileMonitor] = []
        self.bekleyen_kaynak = 0
        self.zaman_kaynagi = 0
        self.sessiz_bitis = 0.0
        self.dongu = GLib.MainLoop()

    # ---------- yaşam döngüsü ----------
    def calistir(self):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self._sinyal_esitle)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGHUP, self._sinyal_yenile)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self._sinyal_dur)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self._sinyal_dur)
        self._durumu_guncelle(calisiyor=False)
        self._izlemeleri_kur()
        self._zamanlayici_kur()
        GLib.timeout_add_seconds(20, self._esitle_baslat)  # açılıştan kısa süre sonra
        log(f"Servis başladı: {len(self.ayar['klasorler'])} klasör, {self.ayar['aralik_dk']} dk aralık")
        self.dongu.run()

    def _sinyal_esitle(self):
        log("İstek: hemen eşitle")
        self._esitle_baslat()
        return GLib.SOURCE_CONTINUE

    def _sinyal_yenile(self):
        log("Ayarlar yeniden okunuyor")
        self.ayar = ortak.ayar_oku()
        self._izlemeleri_kur()
        self._zamanlayici_kur()
        self._esitle_baslat()
        return GLib.SOURCE_CONTINUE

    def _sinyal_dur(self):
        self.dongu.quit()
        return GLib.SOURCE_REMOVE

    # ---------- zamanlama ----------
    def _zamanlayici_kur(self):
        if self.zaman_kaynagi:
            GLib.source_remove(self.zaman_kaynagi)
        dakika = max(1, int(self.ayar.get("aralik_dk", 5)))
        self.zaman_kaynagi = GLib.timeout_add_seconds(dakika * 60, self._esitle_baslat)

    def _izlemeleri_kur(self):
        for m in self.izleyiciler:
            m.cancel()
        self.izleyiciler = []
        for k in self.ayar["klasorler"]:
            kok = ortak.yol(k["yerel"])
            if not kok.is_dir():
                continue
            for dizin, altlar, _ in os.walk(kok):
                altlar[:] = [a for a in altlar if not a.startswith(".")]
                if len(self.izleyiciler) >= EN_FAZLA_IZLEME:
                    break
                try:
                    m = Gio.File.new_for_path(dizin).monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
                except GLib.Error:
                    continue
                m.connect("changed", self._degisiklik)
                self.izleyiciler.append(m)

    def _degisiklik(self, _m, dosya, _diger, olay):
        if time.monotonic() < self.sessiz_bitis or self.kilit.locked():
            return
        if olay not in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.DELETED,
                        Gio.FileMonitorEvent.CREATED, Gio.FileMonitorEvent.MOVED_IN,
                        Gio.FileMonitorEvent.MOVED_OUT, Gio.FileMonitorEvent.RENAMED):
            return
        ad = dosya.get_basename() or ""
        if ad.startswith(".~") or ad.endswith((".part", ".tmp", ".swp", "~")):
            return
        if self.bekleyen_kaynak:
            GLib.source_remove(self.bekleyen_kaynak)
        self.bekleyen_kaynak = GLib.timeout_add_seconds(BEKLEME_SN, self._bekleyen_esitle)

    def _bekleyen_esitle(self):
        self.bekleyen_kaynak = 0
        self._esitle_baslat()
        return GLib.SOURCE_REMOVE

    # ---------- eşitleme ----------
    def _esitle_baslat(self):
        if not self.kilit.locked():
            threading.Thread(target=self._esitle_hepsi, daemon=True).start()
        return GLib.SOURCE_CONTINUE

    def _esitle_hepsi(self):
        if not self.kilit.acquire(blocking=False):
            return
        try:
            istek = ortak.istek_al()
            zorla = set(istek.get("zorla", []))
            self.ayar = ortak.ayar_oku()
            self._durumu_guncelle(calisiyor=True)
            ayar_degisti = False
            for k in self.ayar["klasorler"]:
                if self._esitle(k, k["yerel"] in zorla):
                    ayar_degisti = True
            if ayar_degisti:
                ortak.ayar_yaz(self.ayar)
        finally:
            self.sessiz_bitis = time.monotonic() + SESSIZ_SN
            self._durumu_guncelle(calisiyor=False)
            self.kilit.release()
            GLib.idle_add(self._izlemeleri_kur)

    def _esitle(self, k: dict, zorla: bool) -> bool:
        """Bir klasörü eşitler. Ayar değiştiyse (ilk eşitleme yapıldıysa) True döner."""
        yerel = ortak.yol(k["yerel"])
        uzak = f"{self.ayar['uzak']}:{k['uzak']}"
        kd = self.durum["klasorler"].setdefault(k["yerel"], {})
        kd["calisiyor"] = True
        self._durumu_guncelle(calisiyor=True)

        if not yerel.is_dir():
            yerel.mkdir(parents=True, exist_ok=True)

        ilk = not k.get("hazir")
        sonuc = self._bisync(yerel, uzak, resync=ilk, zorla=zorla)
        if sonuc.returncode != 0 and not ilk and "--resync" in sonuc.stdout + sonuc.stderr:
            # Önceki kayıtlar kaybolmuş: güvenli birleştirme (resync hiçbir şey silmez)
            log(f"{yerel}: kayıtlar bulunamadı, birleştirme yapılıyor")
            sonuc = self._bisync(yerel, uzak, resync=True, zorla=zorla)
            ilk = True

        cikti = sonuc.stdout + sonuc.stderr
        onceki_hata = kd.get("sonuc") == "hata"
        kd.update(calisiyor=False, son=time.time())
        if sonuc.returncode == 0:
            kd.update(sonuc="tamam", mesaj="", silme_siniri=False)
            log(f"{yerel} <-> {uzak}: tamam")
            if ilk:
                k["hazir"] = True
                return True
        else:
            silme = "too many deletes" in cikti.lower() or "max-delete" in cikti.lower()
            mesaj = (f"{self.ayar['en_fazla_silme']}'den fazla dosya silinecekti, güvenlik için durduruldu."
                     if silme else rclone_hata_ozeti(cikti))
            kd.update(sonuc="hata", mesaj=mesaj, silme_siniri=silme)
            log(f"{yerel} <-> {uzak}: HATA: {mesaj}")
            if not onceki_hata:
                bildir(f"Eşitleme hatası: {yerel.name}", mesaj)
        return False

    def _bisync(self, yerel, uzak, resync: bool, zorla: bool) -> subprocess.CompletedProcess:
        komut = ortak.rclone(
            "bisync", str(yerel), uzak,
            "--create-empty-src-dirs", "--resilient", "--recover",
            "--conflict-resolve", "newer", "--conflict-loser", "num",
            "--max-delete", str(self.ayar.get("en_fazla_silme", 50)),
            "--drive-skip-gdocs", "--log-level", "NOTICE",
        )
        if resync:
            komut.append("--resync")
        if zorla:
            komut.append("--force")
        return subprocess.run(komut, capture_output=True, text=True)

    # ---------- durum ----------
    def _durumu_guncelle(self, calisiyor: bool):
        gecerli = {k["yerel"] for k in self.ayar["klasorler"]}
        self.durum["klasorler"] = {y: d for y, d in self.durum["klasorler"].items() if y in gecerli}
        self.durum["calisiyor"] = calisiyor
        self.durum["guncelleme"] = time.time()
        if not calisiyor:
            self.durum["son_esitleme"] = time.time()
            for d in self.durum["klasorler"].values():
                d["calisiyor"] = False
        ortak.durum_yaz(self.durum)


def disk_bagla() -> None:
    """rclone mount'u bu sürecin yerine çalıştırır (systemd Type=notify ile)."""
    ayar = ortak.ayar_oku()
    rclone = ortak.rclone_yolu()
    if not rclone:
        bildir("Drive diski bağlanamadı", "Uygun rclone bulunamadı. Drive Bağlantı'yı açıp kurulumu tamamla.")
        raise SystemExit("rclone bulunamadı")
    nokta = ortak.yol(ayar["baglama_noktasi"])
    if os.path.ismount(nokta):
        subprocess.run(["fusermount3", "-uz", str(nokta)])
    nokta.mkdir(parents=True, exist_ok=True)
    # Google Docs dosyalarının gerçek boyutu bilinmediği için Office biçiminde 0 bayt görünür
    # ve açılamaz; bunun yerine tarayıcıda açılan küçük bağlantı dosyaları gösterilir.
    gdocs = (["--drive-export-formats", "link.html"] if ayar.get("gdocs") == "baglanti"
             else ["--drive-skip-gdocs"])
    os.execv(rclone, [
        rclone, "mount", f"{ayar['uzak']}:", str(nokta),
        "--vfs-cache-mode", "full",
        "--vfs-cache-max-size", f"{ayar.get('onbellek_gb', 10)}G",
        "--vfs-cache-max-age", "720h",
        "--dir-cache-time", "1000h",
        "--poll-interval", "30s",
        "--volname", "Google Drive",
        "--log-level", "NOTICE",
        *gdocs,
    ])


def disk_ayir() -> None:
    nokta = ortak.yol(ortak.ayar_oku()["baglama_noktasi"])
    if os.path.ismount(nokta):
        subprocess.run(["fusermount3", "-uz", str(nokta)])


def main():
    if not ortak.rclone_yolu():
        bildir("Drive eşitlemesi başlatılamadı", "Uygun rclone bulunamadı. Drive Bağlantı'yı açıp kurulumu tamamla.")
        raise SystemExit("rclone bulunamadı")
    Servis().calistir()
