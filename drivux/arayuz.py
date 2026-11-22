"""GTK4 / libadwaita main window."""

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
from .ceviri import DIL_ADLARI, _, _n  # noqa: E402


def gecen_sure(ts: float | None) -> str:
    if not ts:
        return _("not yet")
    s = int(time.time() - ts)
    if s < 60:
        return _("just now")
    if s < 3600:
        return _("{n} min ago").format(n=s // 60)
    if s < 86400:
        return _n("{n} hour ago", "{n} hours ago", s // 3600).format(n=s // 3600)
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def boyut(b: float) -> str:
    for birim in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024 or birim == "TB":
            return f"{b:.1f} {birim}" if birim != "B" else f"{int(b)} B"
        b /= 1024


class Pencere(Adw.ApplicationWindow):
    def __init__(self, uyg):
        super().__init__(application=uyg, title="Drivux", default_width=640, default_height=760)
        self.klasor_satirlari: list[Gtk.Widget] = []
        self.disk_islemde = False

        self.toast = Adw.ToastOverlay()
        gorunum = Adw.ToolbarView()
        baslik = Adw.HeaderBar()
        gorunum.add_top_bar(baslik)

        self.esitle_dugmesi = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text=_("Sync now"))
        self.esitle_dugmesi.connect("clicked", lambda *_a: self.simdi_esitle())
        baslik.pack_start(self.esitle_dugmesi)

        menu = Gio.Menu()
        menu.append(_("Show logs"), "win.kayitlar")
        menu.append(_("Setup wizard"), "win.sihirbaz")
        menu.append(_("About Drivux"), "win.hakkinda")
        baslik.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu))
        for ad, fn in (("kayitlar", self.kayitlari_goster), ("hakkinda", self.hakkinda),
                       ("sihirbaz", lambda: uyg.sihirbazi_ac())):
            eylem = Gio.SimpleAction.new(ad, None)
            eylem.connect("activate", lambda *_a, f=fn: f())
            self.add_action(eylem)

        sayfa = Adw.PreferencesPage()

        # ----- status -----
        durum_grubu = Adw.PreferencesGroup()
        self.durum_satiri = Adw.ActionRow(title=_("Status"))
        self.durum_simgesi = Gtk.Image(icon_size=Gtk.IconSize.LARGE)
        self.durum_satiri.add_prefix(self.durum_simgesi)
        durum_grubu.add(self.durum_satiri)
        sayfa.add(durum_grubu)

        # ----- disk -----
        disk = Adw.PreferencesGroup(
            title=_("Google Drive disk"),
            description=_("Your whole Drive appears in Files like a disk. Files are downloaded as you open them."))
        self.disk_satiri = Adw.ActionRow(title=_("Not mounted"))
        self.disk_satiri.add_prefix(Gtk.Image(icon_name="drive-harddisk-symbolic"))
        self.disk_ac = Gtk.Button(icon_name="folder-open-symbolic", tooltip_text=_("Open in Files"),
                                  valign=Gtk.Align.CENTER, css_classes=["flat"])
        self.disk_ac.connect("clicked", lambda *_a: self.klasoru_ac(ortak.yol(ortak.ayar_oku()["baglama_noktasi"])))
        self.disk_anahtari = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.disk_anahtari.connect("state-set", self.disk_degistir)
        self.disk_satiri.add_suffix(self.disk_ac)
        self.disk_satiri.add_suffix(self.disk_anahtari)
        self.disk_satiri.set_activatable_widget(self.disk_anahtari)
        disk.add(self.disk_satiri)
        sayfa.add(disk)

        # ----- storage -----
        self.alan_grubu = Adw.PreferencesGroup(
            title=_("Storage"),
            description=_("Your Google storage is shared by Drive, Gmail and Google Photos."))
        self.alan_satiri = Adw.ActionRow(title=_("Calculating…"))
        self.alan_cubugu = Gtk.LevelBar(min_value=0, max_value=1, valign=Gtk.Align.CENTER, width_request=160)
        self.alan_satiri.add_suffix(self.alan_cubugu)
        self.alan_grubu.add(self.alan_satiri)
        self.alan_ayrinti = []
        for anahtar, ad in (("used", _("Google Drive")), ("other", _("Gmail and Google Photos")),
                            ("trashed", _("Drive trash")), ("free", _("Free"))):
            s = Adw.ActionRow(title=ad)
            etiket = Gtk.Label(css_classes=["dim-label", "numeric"])
            s.add_suffix(etiket)
            self.alan_grubu.add(s)
            self.alan_ayrinti.append((anahtar, etiket))
        sayfa.add(self.alan_grubu)

        # ----- folders -----
        self.klasor_grubu = Adw.PreferencesGroup(
            title=_("Synced folders"),
            description=_("These folders stay on your computer and open without internet; "
                          "changes are copied in both directions."))
        ekle = Gtk.Button(icon_name="list-add-symbolic", tooltip_text=_("Add folder"),
                          valign=Gtk.Align.CENTER, css_classes=["flat"])
        ekle.connect("clicked", lambda *_a: self.klasor_sec())
        self.klasor_grubu.set_header_suffix(ekle)
        self.bos_satir = Adw.ActionRow(title=_("No folders yet"), subtitle=_("Press + to add one"))
        sayfa.add(self.klasor_grubu)

        # ----- settings -----
        ayar_grubu = Adw.PreferencesGroup(title=_("Settings"))
        ayar = ortak.ayar_oku()
        self.aralik = Adw.SpinRow.new_with_range(1, 120, 1)
        self.aralik.set_title(_("Sync interval"))
        self.aralik.set_subtitle(_("Minutes. Folders are also synced right after a change."))
        self.aralik.set_value(ayar["aralik_dk"])
        self.aralik.connect("notify::value", self.aralik_degisti)
        ayar_grubu.add(self.aralik)
        self.onbellek = Adw.SpinRow.new_with_range(1, 500, 1)
        self.onbellek.set_title(_("Disk cache"))
        self.onbellek.set_subtitle(_("GB. Files opened from the disk take up at most this much space."))
        self.onbellek.set_value(ayar["onbellek_gb"])
        self.onbellek.connect("notify::value", self.onbellek_degisti)
        ayar_grubu.add(self.onbellek)
        self.gdocs = Adw.ComboRow(title=_("Google Docs files (on the disk)"),
                                  subtitle=_("Docs, Sheets and Slides open in Google's editor in your browser"),
                                  model=Gtk.StringList.new([_(e) for _k, e in GDOCS_SECENEKLERI]))
        self.gdocs.set_selected(next((i for i, (k, _e) in enumerate(GDOCS_SECENEKLERI) if k == ayar["gdocs"]), 0))
        self.gdocs.connect("notify::selected", lambda *_a: self._ayari_kaydet(
            "gdocs", GDOCS_SECENEKLERI[self.gdocs.get_selected()][0], sinyal_servise=False, disk_yeniden=True))
        ayar_grubu.add(self.gdocs)
        self.dil = Adw.ComboRow(title=_("Language"), subtitle=_("Takes effect the next time Drivux opens"),
                                model=Gtk.StringList.new([_(ad) for _k, ad in DIL_ADLARI]))
        self.dil.set_selected(next((i for i, (k, _a) in enumerate(DIL_ADLARI) if k == ayar.get("dil", "auto")), 0))
        self.dil.connect("notify::selected", self.dil_degisti)
        ayar_grubu.add(self.dil)
        self.otomatik = Adw.SwitchRow(title=_("Start on login"),
                                      subtitle=_("Sync and the disk start automatically when you log in"))
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
        GLib.timeout_add_seconds(300, lambda: (self.alani_hesapla(), True)[1])

    # ---------- helpers ----------
    def bildir(self, mesaj: str):
        self.toast.add_toast(Adw.Toast(title=mesaj, timeout=3))

    def klasoru_ac(self, yol: Path):
        Gio.AppInfo.launch_default_for_uri(yol.as_uri(), None)

    # ---------- refresh ----------
    def yenile(self):
        ayar = ortak.ayar_oku()
        durum = ortak.durum_oku()
        servis = ortak.servis_aktif(ortak.SERVIS)
        calisiyor = durum.get("calisiyor", False)
        hatalar = [d for d in durum.get("klasorler", {}).values() if d.get("sonuc") == "hata"]

        if not servis:
            simge, baslik, alt = ("dialog-warning-symbolic", _("Sync service is not running"),
                                  _("Turn on \"Start on login\" or run the setup wizard again"))
        elif calisiyor:
            simge, baslik, alt = "emblem-synchronizing-symbolic", _("Syncing…"), _("Copying changes")
        elif hatalar:
            simge, baslik, alt = ("dialog-error-symbolic", _("Sync has a problem"),
                                  _n("{n} folder has an error, see below", "{n} folders have errors, see below",
                                     len(hatalar)).format(n=len(hatalar)))
        else:
            simge, baslik, alt = ("emblem-ok-symbolic", _("Everything is up to date"),
                                  _("Last sync: {when}").format(when=gecen_sure(durum.get("son_esitleme"))))
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
            self.disk_satiri.set_title(_("Mounted") if bagli else _("Not mounted"))
            self.disk_satiri.set_subtitle(ortak.kisalt(ortak.yol(ayar["baglama_noktasi"])))
        self.disk_ac.set_sensitive(bagli)

        # folders: redraw only when something changed (avoids flicker)
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
            satir = self.klasor_satiri(k, kd.get(k["yerel"], {}))
            self.klasor_grubu.add(satir)
            self.klasor_satirlari.append(satir)
        return GLib.SOURCE_CONTINUE

    def klasor_satiri(self, k: dict, d: dict) -> Gtk.Widget:
        yerel = ortak.yol(k["yerel"])
        satir = Adw.ActionRow(title=GLib.markup_escape_text(yerel.name or str(yerel)))
        if d.get("calisiyor"):
            simge, alt = "emblem-synchronizing-symbolic", _("syncing…")
        elif d.get("sonuc") == "hata":
            simge, alt = "dialog-error-symbolic", d.get("mesaj") or _("error")
        elif d.get("sonuc") == "tamam":
            simge, alt = "emblem-ok-symbolic", _("up to date · {when}").format(when=gecen_sure(d.get("son")))
        else:
            simge, alt = "content-loading-symbolic", _("waiting for first sync")
        satir.set_subtitle(GLib.markup_escape_text(f"{ortak.kisalt(yerel)}  ↔  Drive: {k['uzak']}\n{alt}"))
        satir.set_subtitle_lines(3)
        satir.add_prefix(Gtk.Image(icon_name=simge))

        if d.get("silme_siniri"):
            onay = Gtk.Button(label=_("Confirm deletions"), valign=Gtk.Align.CENTER,
                              css_classes=["destructive-action"])
            onay.connect("clicked", lambda *_a: self.silmeleri_onayla(k))
            satir.add_suffix(onay)
        ac = Gtk.Button(icon_name="folder-open-symbolic", tooltip_text=_("Open folder"),
                        valign=Gtk.Align.CENTER, css_classes=["flat"])
        ac.connect("clicked", lambda *_a: self.klasoru_ac(yerel))
        sil = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text=_("Stop syncing"),
                         valign=Gtk.Align.CENTER, css_classes=["flat"])
        sil.connect("clicked", lambda *_a: self.klasor_cikar(k))
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
            if not isinstance(bilgi, dict) or not bilgi.get("total"):
                self.alan_satiri.set_title(_("Could not reach Google Drive"))
                return
            # rclone: used = Drive (trash included), other = Gmail + Google Photos
            toplam = bilgi["total"]
            kullanilan = bilgi.get("used", 0) + bilgi.get("other", 0)
            self.alan_satiri.set_title(_("{used} of {total} used").format(used=boyut(kullanilan),
                                                                          total=boyut(toplam)))
            self.alan_satiri.set_subtitle(_("{p}% full").format(p=round(100 * kullanilan / toplam)))
            self.alan_cubugu.set_value(min(1, kullanilan / toplam))
            for anahtar, etiket in self.alan_ayrinti:
                etiket.set_label(boyut(bilgi.get(anahtar, 0)))
        arka_planda(is_, bitince)

    # ---------- actions ----------
    def simdi_esitle(self):
        ortak.servise_sinyal("USR1")
        self.bildir(_("Sync started"))
        GLib.timeout_add(500, lambda: self.yenile() and False)

    def disk_degistir(self, _anahtar, durum):
        self.disk_islemde = True
        self.disk_satiri.set_title(_("Mounting…") if durum else _("Unmounting…"))
        komut = "start" if durum else "stop"

        def is_():
            r = ortak.systemctl(komut, ortak.DISK_SERVISI)
            if durum:  # wait until it is mounted
                for _i in range(20):
                    if ortak.disk_bagli():
                        break
                    time.sleep(0.5)
            return r

        def bitince(r):
            self.disk_islemde = False
            if r.returncode != 0:
                metin = _("Could not mount the disk: {error}") if durum else _("Could not unmount the disk: {error}")
                self.bildir(metin.format(error=r.stderr.strip()[:80]))
            elif not durum:
                self.bildir(_("Disk unmounted"))
            self.yenile()
        arka_planda(is_, bitince)
        return True  # yenile() sets the real state

    def klasor_sec(self):
        ayar = ortak.ayar_oku()

        def eklendi(k):
            ayar = ortak.ayar_oku()
            ayar["klasorler"].append(k)
            ortak.ayar_yaz(ayar)
            ortak.servise_sinyal("HUP")
            self.bildir(_("{name} added, first sync is starting").format(name=ortak.yol(k["yerel"]).name))
            self.yenile()
        klasor_ekle(self, ayar["klasorler"], ayar["baglama_noktasi"], eklendi)

    def klasor_cikar(self, k: dict):
        dlg = Adw.AlertDialog(
            heading=_("Stop syncing this folder?"),
            body=_("{path} will no longer be synced with Drive.\n"
                   "Files on your computer and on Drive are not deleted.").format(
                path=ortak.kisalt(ortak.yol(k["yerel"]))))
        dlg.add_response("iptal", _("Cancel"))
        dlg.add_response("cikar", _("Stop syncing"))
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
            heading=_("Confirm deletions?"),
            body=_("A lot of files seem to have been deleted. If you deleted them on purpose, confirm and the "
                   "deletions will be applied to the other side too. (Files deleted from Drive stay in "
                   "Drive's trash for 30 days.)\n\nIf it was a mistake, cancel and bring the files back."))
        dlg.add_response("iptal", _("Cancel"))
        dlg.add_response("onayla", _("Confirm and sync"))
        dlg.set_response_appearance("onayla", Adw.ResponseAppearance.DESTRUCTIVE)

        def yanit(_d, r):
            if r == "onayla":
                ortak.istek_ekle(zorla=[k["yerel"]])
                self.bildir(_("Sync started"))
        dlg.connect("response", yanit)
        dlg.present(self)

    def _ayari_kaydet(self, anahtar, deger, sinyal_servise=True, disk_yeniden=False):
        ayar = ortak.ayar_oku()
        ayar[anahtar] = deger
        ortak.ayar_yaz(ayar)
        if sinyal_servise:
            ortak.servise_sinyal("HUP")
        if disk_yeniden and ortak.servis_aktif(ortak.DISK_SERVISI):
            arka_planda(lambda: ortak.systemctl("restart", ortak.DISK_SERVISI))

    def aralik_degisti(self, *_a):
        self._gecikmeli(lambda: self._ayari_kaydet("aralik_dk", int(self.aralik.get_value())))

    def onbellek_degisti(self, *_a):
        self._gecikmeli(lambda: self._ayari_kaydet("onbellek_gb", int(self.onbellek.get_value()),
                                                   sinyal_servise=False, disk_yeniden=True))

    def dil_degisti(self, *_a):
        self._ayari_kaydet("dil", DIL_ADLARI[self.dil.get_selected()][0], sinyal_servise=False)
        self.bildir(_("Language will change the next time Drivux opens"))

    def _gecikmeli(self, fn):
        if self._ayar_zamanlayici:
            GLib.source_remove(self._ayar_zamanlayici)

        def calis():
            self._ayar_zamanlayici = 0
            fn()
            return GLib.SOURCE_REMOVE
        self._ayar_zamanlayici = GLib.timeout_add(800, calis)

    def otomatik_degisti(self, *_a):
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
        metin.get_buffer().set_text(r.stdout or _("No log entries."))
        kaydir = Gtk.ScrolledWindow(child=metin, vexpand=True)
        icerik = Adw.ToolbarView(content=kaydir)
        icerik.add_top_bar(Adw.HeaderBar())
        dlg = Adw.Dialog(title=_("Logs"), content_width=760, content_height=520, child=icerik)
        dlg.present(self)
        GLib.idle_add(lambda: kaydir.get_vadjustment().set_value(kaydir.get_vadjustment().get_upper()))

    def hakkinda(self):
        Adw.AboutDialog(
            application_name="Drivux", application_icon=ortak.UYGULAMA_KIMLIGI,
            version=ortak.SURUM, developer_name="abdullahnil",
            comments=_("A Google Drive client for Linux: mounts Drive as a disk and keeps folders "
                       "in two-way sync (powered by rclone)."),
            website="https://github.com/abdullahnil/drivux",
            issue_url="https://github.com/abdullahnil/drivux/issues",
            license_type=Gtk.License.MIT_X11,
        ).present(self)


class Uygulama(Adw.Application):
    def __init__(self):
        super().__init__(application_id=ortak.UYGULAMA_KIMLIGI, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        if ortak.eski_surumden_tasi() and ortak.ayar_oku()["kurulum_tamam"]:
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
