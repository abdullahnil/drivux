"""Background service: two-way sync of folders with rclone bisync.

- Syncs on a regular interval.
- Syncs a few seconds after something changes in a folder.
- SIGUSR1 syncs right away, SIGHUP reloads the settings.
- Writes results to the status file and shows a desktop notification on errors.
"""

import os
import re
import signal
import subprocess
import threading
import time

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from . import ortak  # noqa: E402
from .ceviri import _  # noqa: E402

BEKLEME_SN = 15          # son değişiklikten sonra eşitlemeden önce beklenecek süre
SESSIZ_SN = 5            # eşitlemeden hemen sonra kendi değişikliklerimizi yok say
EN_FAZLA_IZLEME = 3000   # izlenecek en fazla alt klasör


def log(mesaj: str) -> None:
    print(mesaj, flush=True)


def bildir(baslik: str, govde: str) -> None:
    subprocess.run(
        ["notify-send", "-a", "Drivux", "-i", ortak.UYGULAMA_KIMLIGI, baslik, govde],
        capture_output=True,
    )


_ONEK = re.compile(r"^\d{4}/\d\d/\d\d \d\d:\d\d:\d\d\s+[A-Z]+\s*:\s*")
# rclone'un kendi özet satırları: asıl nedeni söylemezler
_GENEL = ("failed to bisync", "bisync aborted", "bisync critical error",
          "error is retryable", "must run --resync")


def rclone_hata_satirlari(cikti: str) -> list[str]:
    """rclone çıktısındaki hata satırları, zaman damgası ve düzey öneki atılmış."""
    satirlar = []
    for s in cikti.splitlines():
        if "ERROR" in s or "Failed" in s or "error" in s:
            satirlar.append(_ONEK.sub("", s).strip())
    return [s for s in satirlar if s]


def rclone_hata_ozeti(cikti: str) -> str:
    satirlar = rclone_hata_satirlari(cikti)
    ozel = [s for s in satirlar if not any(g in s.lower() for g in _GENEL)]
    if ozel:
        ozet = ozel[-1]
    elif satirlar:
        ozet = satirlar[-1]
    else:
        son = [_ONEK.sub("", s).strip() for s in cikti.strip().splitlines()[-3:]]
        ozet = son[-1] if son else _("Unknown error")
    return ozet[:300] or _("Unknown error")


def _kayitlar_yok(cikti: str) -> bool:
    """bisync önceki kayıtlarını bulamadı mı? ("without --resync" bunu söylemez.)"""
    cikti = cikti.lower()
    return "cannot find prior" in cikti or "must run --resync" in cikti


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
        log(f"Service started: {len(self.ayar['klasorler'])} folder(s), every {self.ayar['aralik_dk']} min")
        self.dongu.run()

    def _sinyal_esitle(self):
        log("Request: sync now")
        self._esitle_baslat()
        return GLib.SOURCE_CONTINUE

    def _sinyal_yenile(self):
        log("Reloading settings")
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
        if sonuc.returncode != 0 and not ilk and _kayitlar_yok(sonuc.stdout + sonuc.stderr):
            # Önceki kayıtlar kaybolmuş: güvenli birleştirme (resync hiçbir şey silmez)
            log(f"{yerel}: previous listings not found, merging (resync)")
            sonuc = self._bisync(yerel, uzak, resync=True, zorla=zorla)
            ilk = True

        cikti = sonuc.stdout + sonuc.stderr
        onceki_hata = kd.get("sonuc") == "hata"
        kd.update(calisiyor=False, son=time.time())
        if sonuc.returncode == 0:
            kd.update(sonuc="tamam", mesaj="", silme_siniri=False)
            log(f"{yerel} <-> {uzak}: ok")
            if ilk:
                k["hazir"] = True
                return True
        else:
            silme = "too many deletes" in cikti.lower() or "max-delete" in cikti.lower()
            mesaj = (_("More than {n} files were about to be deleted, so the sync was stopped to be safe.")
                     .format(n=self.ayar["en_fazla_silme"]) if silme else rclone_hata_ozeti(cikti))
            kd.update(sonuc="hata", mesaj=mesaj, silme_siniri=silme)
            log(f"{yerel} <-> {uzak}: ERROR: {mesaj}")
            for satir in rclone_hata_satirlari(cikti)[-20:]:
                log(f"  rclone: {satir}")
            if not onceki_hata:
                bildir(_("Sync error: {name}").format(name=yerel.name), mesaj)
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
        bildir(_("Couldn't mount the Drive disk"), _("No suitable rclone found. Open Drivux and finish setup."))
        raise SystemExit("rclone not found")
    nokta = ortak.yol(ayar["baglama_noktasi"])
    _eski_baglantiyi_temizle(nokta)
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


def _eski_baglantiyi_temizle(nokta) -> None:
    """Bağlıysa ya da önceki rclone düzgün kapanmadığı için yarım kalmışsa ayırır."""
    try:
        os.stat(nokta)
        yarim = False
    except FileNotFoundError:
        return
    except OSError:          # ENOTCONN: "Transport endpoint is not connected"
        yarim = True
    if yarim or os.path.ismount(nokta):
        subprocess.run(["fusermount3", "-uz", str(nokta)], capture_output=True)


def disk_isit(derinlik: int = 3, paralel: int = 8, en_fazla: int = 5000) -> None:
    """Warms rclone's directory cache right after mounting.

    The file manager lists every subfolder of the folder you open (for item counts),
    and on a cold cache each listing is a Drive API call. Reading the first few
    levels in parallel up front makes browsing instant afterwards. rclone keeps the
    cache fresh by polling Drive for changes.
    """
    from concurrent.futures import ThreadPoolExecutor

    nokta = ortak.yol(ortak.ayar_oku()["baglama_noktasi"])
    for _i in range(120):                       # wait up to a minute for the mount
        if ortak.disk_bagli():
            break
        time.sleep(0.5)
    else:
        return

    def alt_klasorler(yol):
        try:
            with os.scandir(yol) as it:
                return [e.path for e in it if e.is_dir(follow_symlinks=False)]
        except OSError:
            return []

    baslangic = time.monotonic()
    seviye, toplam = [str(nokta)], 0
    with ThreadPoolExecutor(paralel) as havuz:
        for _d in range(derinlik):
            sonraki = []
            for altlar in havuz.map(alt_klasorler, seviye):
                sonraki.extend(altlar)
            toplam += len(seviye)
            seviye = sonraki[:en_fazla]
            if not seviye:
                break
    log(f"Directory cache warmed: {toplam} folders in {time.monotonic() - baslangic:.1f} s")


def disk_ayir() -> None:
    _eski_baglantiyi_temizle(ortak.yol(ortak.ayar_oku()["baglama_noktasi"]))


def main():
    if not ortak.rclone_yolu():
        bildir(_("Couldn't start Drive sync"), _("No suitable rclone found. Open Drivux and finish setup."))
        raise SystemExit("rclone not found")
    Servis().calistir()
