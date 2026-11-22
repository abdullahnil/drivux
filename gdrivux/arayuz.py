"""GTK4 / libadwaita arayüzü."""

import json
import subprocess
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import ortak  # noqa: E402
from .bilesenler import GDOCS_SECENEKLERI, arka_planda, klasor_ekle, servisleri_uygula  # noqa: E402


def gecen_sure(ts: float | None) -> str:
    if not ts:
        return "henüz yok"
    s = int(time.time() - ts)
    if s < 60:
        return "az önce"
    if s < 3600:
        return f"{s // 60} dk önce"
    if s < 86400:
        return f"{s // 3600} saat önce"
    return time.strftime("%d.%m.%Y %H:%M", time.localtime(ts))


def boyut(b: float) -> str:
    for birim in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024 or birim == "TB":
            return f"{b:.1f} {birim}" if birim != "B" else f"{int(b)} B"
        b /= 1024


class Pencere(Adw.ApplicationWindow):
    def __init__(self, uyg):
        super().__init__(application=uyg, title="G-Drivux", default_width=640, default_height=720)
        self.klasor_satirlari: list[Gtk.Widget] = []
        self.disk_islemde = False

        self.toast = Adw.ToastOverlay()
        gorunum = Adw.ToolbarView()
        baslik = Adw.HeaderBar()
        gorunum.add_top_bar(baslik)

        self.esitle_dugmesi = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Şimdi eşitle")
        self.esitle_dugmesi.connect("clicked", lambda *_: self.simdi_esitle())
        baslik.pack_start(self.esitle_dugmesi)

        menu = Gio.Menu()
        menu.append("Kayıtları göster", "win.kayitlar")
        menu.append("Kurulum sihirbazı", "win.sihirbaz")
        menu.append("Hakkında", "win.hakkinda")
        baslik.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu))
        for ad, fn in (("kayitlar", self.kayitlari_goster), ("hakkinda", self.hakkinda),
                       ("sihirbaz", lambda: uyg.sihirbazi_ac())):
            eylem = Gio.SimpleAction.new(ad, None)
            eylem.connect("activate", lambda *_a, f=fn: f())
            self.add_action(eylem)

        sayfa = Adw.PreferencesPage()

        # ----- Durum -----
        self.durum_grubu = Adw.PreferencesGroup()
        self.durum_satiri = Adw.ActionRow(title="Durum")
        self.durum_simgesi = Gtk.Image(icon_size=Gtk.IconSize.LARGE)
        self.durum_satiri.add_prefix(self.durum_simgesi)
        self.durum_grubu.add(self.durum_satiri)
        sayfa.add(self.durum_grubu)

        # ----- Disk -----
        disk = Adw.PreferencesGroup(title="Google Drive diski",
                                    description="Drive'ın tamamı Dosyalar'da bir disk gibi görünür. "
                                                "Dosyalar açıldıkça indirilir.")
        self.disk_satiri = Adw.ActionRow(title="Bağlı değil")
        self.disk_satiri.add_prefix(Gtk.Image(icon_name="drive-harddisk-symbolic"))
        self.disk_ac = Gtk.Button(icon_name="folder-open-symbolic", tooltip_text="Dosyalar'da aç",
                                  valign=Gtk.Align.CENTER, css_classes=["flat"])
        self.disk_ac.connect("clicked", lambda *_: self.klasoru_ac(ortak.yol(ortak.ayar_oku()["baglama_noktasi"])))
        self.disk_anahtari = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.disk_anahtari.connect("state-set", self.disk_degistir)
        self.disk_satiri.add_suffix(self.disk_ac)
        self.disk_satiri.add_suffix(self.disk_anahtari)
        self.disk_satiri.set_activatable_widget(self.disk_anahtari)
        disk.add(self.disk_satiri)
        self.alan_satiri = Adw.ActionRow(title="Kullanılan alan", subtitle="hesaplanıyor…")
        self.alan_cubugu = Gtk.LevelBar(min_value=0, max_value=1, valign=Gtk.Align.CENTER, width_request=160)
        self.alan_satiri.add_suffix(self.alan_cubugu)
        disk.add(self.alan_satiri)
        sayfa.add(disk)

        # ----- Klasörler -----
        self.klasor_grubu = Adw.PreferencesGroup(
            title="Eşitlenen klasörler",
            description="Bu klasörler bilgisayarda da durur, internet olmadan da açılır; "
                        "değişiklikler iki yönde de aktarılır.")
        ekle = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Klasör ekle",
                          valign=Gtk.Align.CENTER, css_classes=["flat"])
        ekle.connect("clicked", lambda *_: self.klasor_sec())
        self.klasor_grubu.set_header_suffix(ekle)
        self.bos_satir = Adw.ActionRow(title="Henüz klasör yok", subtitle="Eklemek için + düğmesine bas")
        sayfa.add(self.klasor_grubu)

        # ----- Ayarlar -----
        ayar_grubu = Adw.PreferencesGroup(title="Ayarlar")
        ayar = ortak.ayar_oku()
        self.aralik = Adw.SpinRow.new_with_range(1, 120, 1)
        self.aralik.set_title("Eşitleme aralığı")
        self.aralik.set_subtitle("Dakika. Klasörde değişiklik olunca ayrıca hemen eşitlenir.")
        self.aralik.set_value(ayar["aralik_dk"])
        self.aralik.connect("notify::value", self.aralik_degisti)
        ayar_grubu.add(self.aralik)
        self.onbellek = Adw.SpinRow.new_with_range(1, 500, 1)
        self.onbellek.set_title("Disk önbelleği")
        self.onbellek.set_subtitle("GB. Diskten açılan dosyalar bilgisayarda en fazla bu kadar yer kaplar.")
        self.onbellek.set_value(ayar["onbellek_gb"])
        self.onbellek.connect("notify::value", self.onbellek_degisti)
        ayar_grubu.add(self.onbellek)
        self.gdocs = Adw.ComboRow(title="Google Docs dosyaları (diskte)",
                                  subtitle="Docs, E-Tablolar ve Slaytlar tarayıcıda Google'ın düzenleyicisinde açılır",
                                  model=Gtk.StringList.new([e for _, e in GDOCS_SECENEKLERI]))
        self.gdocs.set_selected(next((i for i, (k, _) in enumerate(GDOCS_SECENEKLERI) if k == ayar["gdocs"]), 0))
        self.gdocs.connect("notify::selected", lambda *_: self._ayari_kaydet(
            "gdocs", GDOCS_SECENEKLERI[self.gdocs.get_selected()][0], sinyal_servise=False, disk_yeniden=True))
        ayar_grubu.add(self.gdocs)
        self.otomatik = Adw.SwitchRow(title="Oturum açılınca başlat",
                                      subtitle="Eşitleme ve disk bilgisayar açılınca kendiliğinden çalışır")
        self.otomatik.set_active(ortak.systemctl("is-enabled", "--quiet", ortak.SERVIS).returncode == 0)
        self.otomatik.connect("notify::active", self.otomatik_degisti)
        ayar_grubu.add(self.otomatik)
        sayfa.add(ayar_grubu)

        gorunum.set_content(sayfa)
        self.toast.set_child(gorunum)
        self.set_content(self.toast)

        self._ayar_zamanlayici = 0
        self.yenile()
        self.alani_hesapla()
        GLib.timeout_add_seconds(2, self.yenile)

    # ---------- yardımcılar ----------
    def bildir(self, mesaj: str):
        self.toast.add_toast(Adw.Toast(title=mesaj, timeout=3))

    def klasoru_ac(self, yol: Path):
        Gio.AppInfo.launch_default_for_uri(yol.as_uri(), None)

    # ---------- durumu yenile ----------
    def yenile(self):
        ayar = ortak.ayar_oku()
        durum = ortak.durum_oku()
        servis = ortak.servis_aktif(ortak.SERVIS)
        calisiyor = durum.get("calisiyor", False)
        hatalar = [d for d in durum.get("klasorler", {}).values() if d.get("sonuc") == "hata"]

        if not servis:
            simge, baslik, alt = "dialog-warning-symbolic", "Eşitleme servisi çalışmıyor", \
                "\"Oturum açılınca başlat\"ı aç ya da kur.sh'i yeniden çalıştır"
        elif calisiyor:
            simge, baslik, alt = "emblem-synchronizing-symbolic", "Eşitleniyor…", "Değişiklikler aktarılıyor"
        elif hatalar:
            simge, baslik, alt = "dialog-error-symbolic", "Eşitlemede sorun var", \
                f"{len(hatalar)} klasörde hata, aşağıya bak"
        else:
            simge, baslik, alt = "emblem-ok-symbolic", "Her şey güncel", \
                f"Son eşitleme: {gecen_sure(durum.get('son_esitleme'))}"
        self.durum_simgesi.set_from_icon_name(simge)
        self.durum_satiri.set_title(baslik)
        self.durum_satiri.set_subtitle(alt)
        self.esitle_dugmesi.set_sensitive(servis and not calisiyor)

        # disk
        bagli = ortak.disk_bagli(ayar)
        if not self.disk_islemde:
            self.disk_anahtari.handler_block_by_func(self.disk_degistir)
            self.disk_anahtari.set_active(bagli)
            self.disk_anahtari.set_state(bagli)
            self.disk_anahtari.handler_unblock_by_func(self.disk_degistir)
            self.disk_satiri.set_title("Bağlı" if bagli else "Bağlı değil")
            self.disk_satiri.set_subtitle(ortak.kisalt(ortak.yol(ayar["baglama_noktasi"])))
        self.disk_ac.set_sensitive(bagli)

        # klasörler (yalnızca bir şey değiştiyse yeniden çiz; titremeyi önler)
        kd = durum.get("klasorler", {})
        imza = json.dumps([ayar["klasorler"],
                           {y: [d.get("sonuc"), d.get("mesaj"), d.get("calisiyor"), d.get("silme_siniri"),
                                gecen_sure(d.get("son"))] for y, d in kd.items()}], sort_keys=True)
        if imza == getattr(self, "_imza", None):
            return GLib.SOURCE_CONTINUE
        self._imza = imza
        for s in self.klasor_satirlari:
            self.klasor_grubu.remove(s)
        self.klasor_satirlari = []
        if not ayar["klasorler"]:
            self.klasor_grubu.add(self.bos_satir)
            self.klasor_satirlari.append(self.bos_satir)
        for k in ayar["klasorler"]:
            satir = self.klasor_satiri(ayar, k, kd.get(k["yerel"], {}))
            self.klasor_grubu.add(satir)
            self.klasor_satirlari.append(satir)
        return GLib.SOURCE_CONTINUE

    def klasor_satiri(self, ayar: dict, k: dict, d: dict) -> Gtk.Widget:
        yerel = ortak.yol(k["yerel"])
        satir = Adw.ActionRow(title=GLib.markup_escape_text(yerel.name or str(yerel)))
        uzak = f"Drive: {k['uzak']}"
        if d.get("calisiyor"):
            simge, alt = "emblem-synchronizing-symbolic", "eşitleniyor…"
        elif d.get("sonuc") == "hata":
            simge, alt = "dialog-error-symbolic", d.get("mesaj", "hata")
        elif d.get("sonuc") == "tamam":
            simge, alt = "emblem-ok-symbolic", f"güncel · {gecen_sure(d.get('son'))}"
        else:
            simge, alt = "content-loading-symbolic", "ilk eşitleme bekleniyor"
        satir.set_subtitle(GLib.markup_escape_text(f"{ortak.kisalt(yerel)}  ↔  {uzak}\n{alt}"))
        satir.set_subtitle_lines(3)
        satir.add_prefix(Gtk.Image(icon_name=simge))

        if d.get("silme_siniri"):
            onay = Gtk.Button(label="Silmeleri onayla", valign=Gtk.Align.CENTER,
                              css_classes=["destructive-action"])
            onay.connect("clicked", lambda *_: self.silmeleri_onayla(k))
            satir.add_suffix(onay)
        ac = Gtk.Button(icon_name="folder-open-symbolic", tooltip_text="Klasörü aç",
                        valign=Gtk.Align.CENTER, css_classes=["flat"])
        ac.connect("clicked", lambda *_: self.klasoru_ac(yerel))
        sil = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Eşitlemeden çıkar",
                         valign=Gtk.Align.CENTER, css_classes=["flat"])
        sil.connect("clicked", lambda *_: self.klasor_cikar(k))
        satir.add_suffix(ac)
        satir.add_suffix(sil)
        return satir

    def alani_hesapla(self):
        uzak = ortak.ayar_oku()["uzak"]

        def is_():
            r = subprocess.run(ortak.rclone("about", f"{uzak}:", "--json"), capture_output=True, text=True)
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError:
                return None

        def bitince(bilgi):
            if bilgi and bilgi.get("total"):
                self.alan_satiri.set_subtitle(f"{boyut(bilgi['used'])} / {boyut(bilgi['total'])}  "
                                              f"(çöp kutusu: {boyut(bilgi.get('trashed', 0))})")
                self.alan_cubugu.set_value(bilgi["used"] / bilgi["total"])
            else:
                self.alan_satiri.set_subtitle("Drive'a ulaşılamadı")
        arka_planda(is_, bitince)

    # ---------- eylemler ----------
    def simdi_esitle(self):
        ortak.servise_sinyal("USR1")
        self.bildir("Eşitleme başlatıldı")
        GLib.timeout_add(500, lambda: self.yenile() and False)

    def disk_degistir(self, anahtar, durum):
        self.disk_islemde = True
        self.disk_satiri.set_title("Bağlanıyor…" if durum else "Ayrılıyor…")
        komut = "start" if durum else "stop"

        def is_():
            r = ortak.systemctl(komut, ortak.DISK_SERVISI)
            if durum:  # bağlanmasını bekle
                for _ in range(20):
                    if ortak.disk_bagli():
                        break
                    time.sleep(0.5)
            return r

        def bitince(r):
            self.disk_islemde = False
            if r.returncode != 0:
                self.bildir("Disk " + ("bağlanamadı" if durum else "ayrılamadı") + ": " + r.stderr.strip()[:80])
            elif not durum:
                self.bildir("Disk ayrıldı")
            self.yenile()
        arka_planda(is_, bitince)
        return True  # durumu yenile() belirler

    def klasor_sec(self):
        ayar = ortak.ayar_oku()

        def eklendi(k):
            ayar = ortak.ayar_oku()
            ayar["klasorler"].append(k)
            ortak.ayar_yaz(ayar)
            ortak.servise_sinyal("HUP")
            self.bildir(f"{ortak.yol(k['yerel']).name} eklendi, ilk eşitleme başlıyor")
            self.yenile()
        klasor_ekle(self, ayar["klasorler"], ayar["baglama_noktasi"], eklendi)

    def klasor_cikar(self, k: dict):
        dlg = Adw.AlertDialog(
            heading="Eşitlemeden çıkarılsın mı?",
            body=f"{ortak.kisalt(ortak.yol(k['yerel']))} artık Drive ile eşitlenmeyecek.\n"
                 "Bilgisayardaki ve Drive'daki dosyalar silinmez.")
        dlg.add_response("iptal", "İptal")
        dlg.add_response("cikar", "Çıkar")
        dlg.set_response_appearance("cikar", Adw.ResponseAppearance.DESTRUCTIVE)

        def yanit(_d, r):
            if r != "cikar":
                return
            ayar = ortak.ayar_oku()
            ayar["klasorler"] = [x for x in ayar["klasorler"] if x["yerel"] != k["yerel"]]
            ortak.ayar_yaz(ayar)
            ortak.servise_sinyal("HUP")
            self.yenile()
        dlg.connect("response", yanit)
        dlg.present(self)

    def silmeleri_onayla(self, k: dict):
        dlg = Adw.AlertDialog(
            heading="Silmeler onaylansın mı?",
            body="Çok sayıda dosya silinmiş görünüyor. Bilerek sildiysen onayla; silmeler karşı tarafa da "
                 "uygulanır. (Drive'dan silinenler 30 gün boyunca Drive çöp kutusunda durur.)\n\n"
                 "Yanlışlıkla olduysa iptal et ve dosyaları geri getir.")
        dlg.add_response("iptal", "İptal")
        dlg.add_response("onayla", "Onayla ve eşitle")
        dlg.set_response_appearance("onayla", Adw.ResponseAppearance.DESTRUCTIVE)

        def yanit(_d, r):
            if r == "onayla":
                ortak.istek_ekle(zorla=[k["yerel"]])
                self.bildir("Eşitleme başlatıldı")
        dlg.connect("response", yanit)
        dlg.present(self)

    def _ayari_kaydet(self, anahtar, deger, sinyal_servise=True, disk_yeniden=False):
        ayar = ortak.ayar_oku()
        ayar[anahtar] = deger
        ortak.ayar_yaz(ayar)
        if sinyal_servise:
            ortak.servise_sinyal("HUP")
        if disk_yeniden and ortak.servis_aktif(ortak.DISK_SERVISI):
            arka_planda(lambda: ortak.systemctl("restart", ortak.DISK_SERVISI), lambda _r: None)

    def aralik_degisti(self, *_):
        self._gecikmeli(lambda: self._ayari_kaydet("aralik_dk", int(self.aralik.get_value())))

    def onbellek_degisti(self, *_):
        self._gecikmeli(lambda: self._ayari_kaydet("onbellek_gb", int(self.onbellek.get_value()),
                                                   sinyal_servise=False, disk_yeniden=True))

    def _gecikmeli(self, fn):
        if self._ayar_zamanlayici:
            GLib.source_remove(self._ayar_zamanlayici)

        def calis():
            self._ayar_zamanlayici = 0
            fn()
            return GLib.SOURCE_REMOVE
        self._ayar_zamanlayici = GLib.timeout_add(800, calis)

    def otomatik_degisti(self, *_):
        if self.otomatik.get_active():
            arka_planda(lambda: servisleri_uygula(ortak.ayar_oku()), lambda _r: self.yenile())
        else:
            arka_planda(lambda: ortak.systemctl("disable", ortak.SERVIS, ortak.DISK_SERVISI),
                        lambda _r: self.yenile())

    def kayitlari_goster(self):
        r = subprocess.run(["journalctl", "--user", "-u", ortak.SERVIS, "-u", ortak.DISK_SERVISI,
                            "-n", "300", "--no-pager", "-o", "short"], capture_output=True, text=True)
        metin = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                             top_margin=12, bottom_margin=12, left_margin=12, right_margin=12)
        metin.get_buffer().set_text(r.stdout or "Kayıt yok.")
        kaydir = Gtk.ScrolledWindow(child=metin, vexpand=True)
        icerik = Adw.ToolbarView(content=kaydir)
        icerik.add_top_bar(Adw.HeaderBar())
        dlg = Adw.Dialog(title="Kayıtlar", content_width=760, content_height=520, child=icerik)
        dlg.present(self)
        GLib.idle_add(lambda: kaydir.get_vadjustment().set_value(kaydir.get_vadjustment().get_upper()))

    def hakkinda(self):
        Adw.AboutDialog(
            application_name="G-Drivux", application_icon=ortak.UYGULAMA_KIMLIGI,
            version=ortak.SURUM, developer_name="abdullahnil",
            comments="Google Drive'ı disk olarak bağlar ve klasörleri iki yönlü eşitler (rclone).",
            website="https://github.com/abdullahnil/gdrivux",
            license_type=Gtk.License.MIT_X11,
        ).present(self)


class Uygulama(Adw.Application):
    def __init__(self):
        super().__init__(application_id=ortak.UYGULAMA_KIMLIGI, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        if ortak.eski_surumden_tasi() and ortak.ayar_oku()["kurulum_tamam"]:
            from .bilesenler import servisleri_uygula
            servisleri_uygula(ortak.ayar_oku())
        if self.props.active_window:
            self.props.active_window.present()
        elif not ortak.ayar_oku()["kurulum_tamam"] or not ortak.rclone_yolu():
            self.sihirbazi_ac()
        else:
            Pencere(self).present()

    def sihirbazi_ac(self):
        from .sihirbaz import Sihirbaz
        for p in self.get_windows():
            if isinstance(p, Pencere):
                p.close()
        Sihirbaz(self, lambda: Pencere(self).present()).present()


def main():
    return Uygulama().run([])
