"""First-run setup wizard.

Steps: welcome → rclone → Google account → disk → folders → summary → done
"""

import re
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import ortak, rclone_kur  # noqa: E402
from .bilesenler import GDOCS_SECENEKLERI, arka_planda, klasor_ekle, servisleri_uygula  # noqa: E402
from .ceviri import _  # noqa: E402

CLIENT_ID_REHBERI = "https://rclone.org/drive/#making-your-own-client-id"


class Sihirbaz(Adw.ApplicationWindow):
    def __init__(self, uyg, bitince):
        super().__init__(application=uyg, title=_("Drivux Setup"), default_width=620, default_height=700)
        self.bitince = bitince
        self.ayar = ortak.ayar_oku()
        self.hesap_hazir = False
        self.giris_sureci: subprocess.Popen | None = None
        self.mesgul = False

        self.toast = Adw.ToastOverlay()
        gorunum = Adw.ToolbarView()
        self.baslik = Adw.WindowTitle(title=_("Setup"))
        gorunum.add_top_bar(Adw.HeaderBar(title_widget=self.baslik))

        self.yigin = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, vexpand=True)
        self.sayfalar = [
            ("hosgeldin", self.sayfa_hosgeldin()),
            ("rclone", self.sayfa_rclone()),
            ("hesap", self.sayfa_hesap()),
            ("disk", self.sayfa_disk()),
            ("klasorler", self.sayfa_klasorler()),
            ("ozet", self.sayfa_ozet()),
            ("bitti", self.sayfa_bitti()),
        ]
        for ad, s in self.sayfalar:
            self.yigin.add_named(s, ad)
        gorunum.set_content(self.yigin)

        alt = Gtk.CenterBox(margin_start=12, margin_end=12, margin_top=12, margin_bottom=12)
        self.geri = Gtk.Button(label=_("Back"))
        self.geri.connect("clicked", lambda *_a: self.git(self.sira - 1))
        self.ileri = Gtk.Button(label=_("Next"), css_classes=["suggested-action"])
        self.ileri.connect("clicked", lambda *_a: self.ileri_bas())
        alt.set_start_widget(self.geri)
        alt.set_end_widget(self.ileri)
        gorunum.add_bottom_bar(alt)

        self.toast.set_child(gorunum)
        self.set_content(self.toast)
        self.connect("close-request", self._kapaniyor)
        self.sira = 0
        self.git(0)

    # ---------- navigation ----------
    def git(self, sira: int):
        sira = max(0, min(sira, len(self.sayfalar) - 1))
        self.yigin.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT if sira > self.sira
                                       else Gtk.StackTransitionType.SLIDE_RIGHT)
        self.sira = sira
        ad = self.sayfalar[sira][0]
        self.yigin.set_visible_child_name(ad)
        adim_sayisi = len(self.sayfalar) - 2
        self.baslik.set_subtitle(_("Step {n} of {total}").format(n=sira, total=adim_sayisi)
                                 if 0 < sira <= adim_sayisi else "")
        if ad == "rclone":
            self.rclone_kontrol()
        elif ad == "hesap":
            self.hesap_kontrol()
        elif ad == "ozet":
            self.ozeti_doldur()
        self.dugmeleri_guncelle()

    def dugmeleri_guncelle(self):
        ad = self.sayfalar[self.sira][0]
        self.geri.set_visible(ad not in ("hosgeldin", "bitti"))
        self.geri.set_sensitive(not self.mesgul)
        etiket = {"hosgeldin": _("Get started"), "ozet": _("Set up"), "bitti": _("Open Drivux")}.get(ad, _("Next"))
        self.ileri.set_label(etiket)
        izin = not self.mesgul
        if ad == "rclone":
            izin = izin and ortak.rclone_yolu() is not None
        elif ad == "hesap":
            izin = izin and self.hesap_hazir
        elif ad == "disk":
            izin = izin and (not self.disk_anahtari.get_active() or bool(self.nokta_girisi.get_text().strip()))
        self.ileri.set_sensitive(izin)

    def ileri_bas(self):
        ad = self.sayfalar[self.sira][0]
        if ad == "disk":
            self.ayar["disk"] = self.disk_anahtari.get_active()
            self.ayar["baglama_noktasi"] = ortak.kisalt(ortak.yol(self.nokta_girisi.get_text().strip()))
            self.ayar["gdocs"] = GDOCS_SECENEKLERI[self.gdocs_secimi.get_selected()][0]
            self.ayar["onbellek_gb"] = int(self.onbellek.get_value())
        elif ad == "klasorler":
            self.ayar["aralik_dk"] = int(self.aralik.get_value())
        if ad == "ozet":
            self.uygula()
        elif ad == "bitti":
            self.close()
            self.bitince()
        else:
            self.git(self.sira + 1)

    def _kapaniyor(self, *_a):
        if self.giris_sureci and self.giris_sureci.poll() is None:
            self.giris_sureci.terminate()
        return False

    def bildir(self, metin):
        self.toast.add_toast(Adw.Toast(title=metin, timeout=4))

    # ---------- pages ----------
    def sayfa_hosgeldin(self):
        return Adw.StatusPage(
            icon_name=ortak.UYGULAMA_KIMLIGI,
            title=_("Welcome to Drivux"),
            description=_("In a few steps we'll connect Google Drive to this computer:\n\n"
                          "• Your whole Drive will appear in Files like a disk\n"
                          "• The folders you choose will stay in two-way sync with Drive\n\n"
                          "Everything you need is installed from this wizard."))

    def sayfa_rclone(self):
        sayfa = Adw.PreferencesPage()
        grup = Adw.PreferencesGroup(
            title="rclone",
            description=_("Drivux talks to Google Drive through rclone, an open-source tool. "
                          "Version {version} or newer is needed.").format(
                version=ortak.surum_metni(ortak.EN_DUSUK_RCLONE)))
        self.rclone_satiri = Adw.ActionRow(title=_("Checking…"))
        self.rclone_simgesi = Gtk.Image(icon_size=Gtk.IconSize.LARGE)
        self.rclone_satiri.add_prefix(self.rclone_simgesi)
        grup.add(self.rclone_satiri)
        self.rclone_dugmesi = Gtk.Button(label=_("Download and install rclone"), halign=Gtk.Align.CENTER,
                                         css_classes=["suggested-action", "pill"], margin_top=18)
        self.rclone_dugmesi.connect("clicked", lambda *_a: self.rclone_indir())
        self.rclone_ilerleme = Gtk.ProgressBar(visible=False, margin_top=18, show_text=True)
        aciklama = Gtk.Label(
            label=_("rclone is downloaded from its official site (downloads.rclone.org), verified, and "
                    "installed for your user only. No administrator password is needed."),
            wrap=True, css_classes=["dim-label", "caption"], margin_top=12, justify=Gtk.Justification.CENTER)
        kutu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        kutu.append(self.rclone_dugmesi)
        kutu.append(self.rclone_ilerleme)
        kutu.append(aciklama)
        grup2 = Adw.PreferencesGroup()
        grup2.add(kutu)
        sayfa.add(grup)
        sayfa.add(grup2)
        return sayfa

    def sayfa_hesap(self):
        sayfa = Adw.PreferencesPage()
        grup = Adw.PreferencesGroup(
            title=_("Google account"),
            description=_("Google sign-in will open in your browser. Choose your account and allow access; "
                          "your password never reaches this app."))
        self.ad_girisi = Adw.EntryRow(title=_("Connection name"), text=self.ayar["uzak"])
        self.ad_girisi.connect("changed", lambda *_a: self.hesap_kontrol())
        grup.add(self.ad_girisi)
        self.hesap_satiri = Adw.ActionRow(title="")
        self.hesap_simgesi = Gtk.Image()
        self.hesap_satiri.add_prefix(self.hesap_simgesi)
        grup.add(self.hesap_satiri)
        sayfa.add(grup)

        gelismis = Adw.PreferencesGroup()
        self.client_genisleyen = Adw.ExpanderRow(
            title=_("Use your own Google client ID (recommended)"),
            subtitle=_("rclone's shared ID is being retired; with your own, your connection keeps working"),
            show_enable_switch=True, enable_expansion=False)
        self.client_id = Adw.EntryRow(title="Client ID")
        self.client_secret = Adw.PasswordEntryRow(title="Client secret")
        rehber = Adw.ActionRow(title=_("How do I create one?"), subtitle=_("Open the rclone guide in your browser"),
                               activatable=True)
        rehber.add_suffix(Gtk.Image(icon_name="web-browser-symbolic"))
        rehber.connect("activated", lambda *_a: Gio.AppInfo.launch_default_for_uri(CLIENT_ID_REHBERI, None))
        for r in (self.client_id, self.client_secret, rehber):
            self.client_genisleyen.add_row(r)
        gelismis.add(self.client_genisleyen)
        sayfa.add(gelismis)

        dugme_grubu = Adw.PreferencesGroup()
        kutu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, halign=Gtk.Align.CENTER)
        self.giris_dugmesi = Gtk.Button(label=_("Sign in with Google"), css_classes=["suggested-action", "pill"])
        self.giris_dugmesi.connect("clicked", lambda *_a: self.google_giris())
        self.giris_bekleme = Gtk.Box(spacing=8, visible=False, halign=Gtk.Align.CENTER)
        self.giris_bekleme.append(Gtk.Spinner(spinning=True))
        self.giris_bekleme.append(Gtk.Label(label=_("Finish signing in in your browser…")))
        iptal = Gtk.Button(label=_("Cancel"), css_classes=["flat"])
        iptal.connect("clicked", lambda *_a: self.giris_iptal())
        self.giris_bekleme.append(iptal)
        kutu.append(self.giris_dugmesi)
        kutu.append(self.giris_bekleme)
        dugme_grubu.add(kutu)
        sayfa.add(dugme_grubu)
        return sayfa

    def sayfa_disk(self):
        sayfa = Adw.PreferencesPage()
        grup = Adw.PreferencesGroup(
            title=_("Google Drive disk"),
            description=_("Your whole Drive appears in Files like a disk. Files are downloaded as you open "
                          "them and only use as much space as the cache allows."))
        self.disk_anahtari = Adw.SwitchRow(title=_("Mount Drive as a disk"), active=self.ayar["disk"])
        self.disk_anahtari.connect("notify::active", lambda *_a: self._disk_secenekleri())
        grup.add(self.disk_anahtari)

        self.nokta_girisi = Adw.EntryRow(title=_("Mount folder"), text=self.ayar["baglama_noktasi"])
        self.nokta_girisi.connect("changed", lambda *_a: self.dugmeleri_guncelle())
        sec = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER, css_classes=["flat"],
                         tooltip_text=_("Choose folder"))
        sec.connect("clicked", lambda *_a: self._nokta_sec())
        self.nokta_girisi.add_suffix(sec)
        grup.add(self.nokta_girisi)

        self.gdocs_secimi = Adw.ComboRow(
            title=_("Google Docs, Sheets and Slides"),
            subtitle=_("Double-click a shortcut to open the file in Google's own editor in your browser"),
            model=Gtk.StringList.new([_(e) for _k, e in GDOCS_SECENEKLERI]))
        self.gdocs_secimi.set_selected(next((i for i, (k, _e) in enumerate(GDOCS_SECENEKLERI)
                                             if k == self.ayar["gdocs"]), 0))
        grup.add(self.gdocs_secimi)

        self.onbellek = Adw.SpinRow.new_with_range(1, 500, 1)
        self.onbellek.set_title(_("Cache limit (GB)"))
        self.onbellek.set_subtitle(_("Files opened from the disk take up at most this much space"))
        self.onbellek.set_value(self.ayar["onbellek_gb"])
        grup.add(self.onbellek)
        sayfa.add(grup)
        self._disk_secenekleri()
        return sayfa

    def _disk_secenekleri(self):
        acik = self.disk_anahtari.get_active()
        for w in (self.nokta_girisi, self.gdocs_secimi, self.onbellek):
            w.set_sensitive(acik)
        if hasattr(self, "ileri"):
            self.dugmeleri_guncelle()

    def _nokta_sec(self):
        def secildi(d, sonuc):
            try:
                self.nokta_girisi.set_text(ortak.kisalt(d.select_folder_finish(sonuc).get_path()))
            except GLib.Error:
                pass
        Gtk.FileDialog(title=_("Folder to mount Drive in")).select_folder(self, None, secildi)

    def sayfa_klasorler(self):
        sayfa = Adw.PreferencesPage()
        self.klasor_grubu = Adw.PreferencesGroup(
            title=_("Folders to sync (optional)"),
            description=_("These folders stay on your computer, open without internet, and changes are "
                          "copied in both directions. You can also add them later from the app."))
        ekle = Gtk.Button(icon_name="list-add-symbolic", tooltip_text=_("Add folder"),
                          valign=Gtk.Align.CENTER, css_classes=["flat"])
        ekle.connect("clicked", lambda *_a: klasor_ekle(self, self.ayar["klasorler"],
                                                        self.nokta_girisi.get_text(), self._klasor_eklendi,
                                                        uzak_ad=self.ayar["uzak"]))
        self.klasor_grubu.set_header_suffix(ekle)
        self.klasor_satirlari = []
        sayfa.add(self.klasor_grubu)

        ayar_grubu = Adw.PreferencesGroup()
        self.aralik = Adw.SpinRow.new_with_range(1, 120, 1)
        self.aralik.set_title(_("Sync interval (minutes)"))
        self.aralik.set_subtitle(_("Folders are also synced a few seconds after a change"))
        self.aralik.set_value(self.ayar["aralik_dk"])
        ayar_grubu.add(self.aralik)
        sayfa.add(ayar_grubu)
        self._klasorleri_ciz()
        return sayfa

    def _klasor_eklendi(self, k):
        self.ayar["klasorler"].append(k)
        self._klasorleri_ciz()

    def _klasor_sil(self, k):
        self.ayar["klasorler"].remove(k)
        self._klasorleri_ciz()

    def _klasorleri_ciz(self):
        for s in self.klasor_satirlari:
            self.klasor_grubu.remove(s)
        self.klasor_satirlari = []
        if not self.ayar["klasorler"]:
            s = Adw.ActionRow(title=_("No folders yet"), subtitle=_("Press + to add one"))
            self.klasor_grubu.add(s)
            self.klasor_satirlari.append(s)
        for k in self.ayar["klasorler"]:
            s = Adw.ActionRow(title=GLib.markup_escape_text(ortak.kisalt(ortak.yol(k["yerel"]))),
                              subtitle=GLib.markup_escape_text(f"Drive: {k['uzak']}"))
            s.add_prefix(Gtk.Image(icon_name="folder-symbolic"))
            sil = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER, css_classes=["flat"],
                             tooltip_text=_("Remove"))
            sil.connect("clicked", lambda *_a, k=k: self._klasor_sil(k))
            s.add_suffix(sil)
            self.klasor_grubu.add(s)
            self.klasor_satirlari.append(s)

    def sayfa_ozet(self):
        sayfa = Adw.PreferencesPage()
        self.ozet_grubu = Adw.PreferencesGroup(
            title=_("Summary"),
            description=_("Press \"Set up\" to save the settings and start the services. "
                          "You can change all of this later."))
        self.ozet_satirlari = []
        sayfa.add(self.ozet_grubu)
        return sayfa

    def ozeti_doldur(self):
        for s in self.ozet_satirlari:
            self.ozet_grubu.remove(s)
        a = self.ayar
        if a["disk"]:
            disk = _("{path} · cache {gb} GB · Google Docs: {docs}").format(
                path=a["baglama_noktasi"], gb=a["onbellek_gb"], docs=_(dict(GDOCS_SECENEKLERI)[a["gdocs"]]).lower())
        else:
            disk = _("won't be mounted")
        satirlar = [
            (_("Google account"), _("rclone connection: {name}").format(name=a["uzak"])),
            (_("Drive disk"), disk),
            (_("Synced folders"), "\n".join(f"{k['yerel']}  ↔  Drive: {k['uzak']}" for k in a["klasorler"])
             or _("none (you can add them later)")),
            (_("Sync interval"), _("{n} minutes").format(n=a["aralik_dk"])),
            (_("Start on login"), _("Sync and the disk start automatically when you log in")),
        ]
        self.ozet_satirlari = []
        for baslik, alt in satirlar:
            s = Adw.ActionRow(title=baslik, subtitle=GLib.markup_escape_text(alt), subtitle_selectable=True)
            s.set_subtitle_lines(0)
            self.ozet_grubu.add(s)
            self.ozet_satirlari.append(s)

    def sayfa_bitti(self):
        self.bitti_sayfasi = Adw.StatusPage(icon_name="emblem-ok-symbolic", title=_("All set!"))
        return self.bitti_sayfasi

    # ---------- rclone step ----------
    def rclone_kontrol(self):
        def is_():
            return ortak.rclone_yolu(yenile=True), ortak.rclone_adaylari()

        def bitti(sonuc):
            if isinstance(sonuc, Exception):
                sonuc = (None, [])
            yol, adaylar = sonuc
            if yol:
                surum = dict(adaylar).get(yol)
                self.rclone_simgesi.set_from_icon_name("emblem-ok-symbolic")
                self.rclone_satiri.set_title(_("rclone {version} is ready").format(
                    version=ortak.surum_metni(surum)))
                self.rclone_satiri.set_subtitle(ortak.kisalt(yol))
                self.rclone_dugmesi.set_visible(False)
            else:
                eski = [f"{ortak.kisalt(y)} ({ortak.surum_metni(s)})" for y, s in adaylar]
                self.rclone_simgesi.set_from_icon_name("dialog-warning-symbolic")
                self.rclone_satiri.set_title(_("Installed rclone is too old") if eski
                                             else _("No suitable rclone found"))
                self.rclone_satiri.set_subtitle(_("Found: {list}").format(list=", ".join(eski)) if eski
                                                else _("You can install it with the button below"))
                self.rclone_dugmesi.set_visible(True)
            self.dugmeleri_guncelle()
        arka_planda(is_, bitti)

    def rclone_indir(self):
        self.mesgul = True
        self.dugmeleri_guncelle()
        self.rclone_dugmesi.set_sensitive(False)
        self.rclone_ilerleme.set_visible(True)
        self.rclone_ilerleme.set_fraction(0)

        def ilerleme(oran):
            GLib.idle_add(self.rclone_ilerleme.set_fraction, oran)

        def durum(metin):
            GLib.idle_add(self.rclone_ilerleme.set_text, metin)

        def bitti(sonuc):
            self.mesgul = False
            self.rclone_dugmesi.set_sensitive(True)
            if isinstance(sonuc, Exception):
                self.rclone_ilerleme.set_visible(False)
                self.bildir(_("Installation failed: {error}").format(error=sonuc))
            else:
                self.rclone_ilerleme.set_fraction(1)
            self.rclone_kontrol()
        arka_planda(lambda: rclone_kur.kur(ilerleme, durum), bitti)

    # ---------- account step ----------
    def _ad(self) -> str:
        return self.ad_girisi.get_text().strip()

    def hesap_kontrol(self):
        ad = self._ad()
        self.hesap_hazir = False
        if not re.fullmatch(r"[A-Za-z0-9_-]+", ad or "-!"):
            self.hesap_simgesi.set_from_icon_name("dialog-warning-symbolic")
            self.hesap_satiri.set_title(_("Invalid name"))
            self.hesap_satiri.set_subtitle(_("Use only English letters, digits, - and _"))
            self.giris_dugmesi.set_sensitive(False)
            self.dugmeleri_guncelle()
            return
        self.giris_dugmesi.set_sensitive(self.giris_sureci is None)

        def bitti(mevcut):
            if isinstance(mevcut, Exception):
                mevcut = []
            if self._ad() != ad:
                return
            if ad in mevcut:
                self.hesap_hazir = True
                self.hesap_simgesi.set_from_icon_name("emblem-ok-symbolic")
                self.hesap_satiri.set_title(_("A Google Drive connection with this name already exists"))
                self.hesap_satiri.set_subtitle(_("You can use it; type a different name for another account"))
                self.giris_dugmesi.set_visible(False)
            else:
                self.hesap_simgesi.set_from_icon_name("dialog-information-symbolic")
                self.hesap_satiri.set_title(_("Not connected yet"))
                self.hesap_satiri.set_subtitle(_("Connect your Google account with the button below"))
                self.giris_dugmesi.set_visible(self.giris_sureci is None)
            self.dugmeleri_guncelle()
        arka_planda(ortak.drive_hesaplari, bitti)

    def google_giris(self):
        ad = self._ad()
        komut = ortak.rclone("config", "create", ad, "drive", "scope=drive")
        if self.client_genisleyen.get_enable_expansion():
            cid, sec = self.client_id.get_text().strip(), self.client_secret.get_text().strip()
            if not cid or not sec:
                self.bildir(_("Enter both the client ID and secret, or turn this option off"))
                return
            komut += [f"client_id={cid}", f"client_secret={sec}"]
        self.giris_dugmesi.set_visible(False)
        self.giris_bekleme.set_visible(True)
        self.ad_girisi.set_sensitive(False)
        self.mesgul = True
        self.dugmeleri_guncelle()
        # rclone opens the browser itself and waits for Google's answer on a local address
        self.giris_sureci = subprocess.Popen(komut, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        surec = self.giris_sureci

        def bitti(sonuc):
            if isinstance(sonuc, Exception):
                sonuc = (str(sonuc), 1)
            cikti, kod = sonuc
            self.giris_sureci = None
            self.mesgul = False
            self.giris_bekleme.set_visible(False)
            self.ad_girisi.set_sensitive(True)
            if kod == 0:
                self.ayar["uzak"] = ad
                self.bildir(_("Google account connected"))
            elif kod > 0:
                son = [s for s in cikti.splitlines() if s.strip()][-1:] or [_("unknown error")]
                self.bildir(_("Sign-in didn't finish: {error}").format(error=son[0][:120]))
            self.hesap_kontrol()
        arka_planda(lambda: (surec.communicate()[0], surec.returncode), bitti)

    def giris_iptal(self):
        if self.giris_sureci:
            self.giris_sureci.terminate()

    # ---------- apply ----------
    def uygula(self):
        self.mesgul = True
        self.dugmeleri_guncelle()
        self.ileri.set_label(_("Setting up…"))
        self.ayar["kurulum_tamam"] = True
        ortak.ayar_yaz(self.ayar)

        def bitti(hatalar):
            self.mesgul = False
            if isinstance(hatalar, Exception):
                hatalar = [str(hatalar)]
            if hatalar:
                self.bitti_sayfasi.set_icon_name("dialog-warning-symbolic")
                self.bitti_sayfasi.set_title(_("Set up, but some services didn't start"))
                self.bitti_sayfasi.set_description("\n".join(hatalar))
            else:
                parca = []
                if self.ayar["disk"]:
                    parca.append(_("Google Drive now appears as \"Google Drive\" in the Files sidebar "
                                   "({path}).").format(path=self.ayar["baglama_noktasi"]))
                if self.ayar["klasorler"]:
                    parca.append(_("The first sync of your folders has started; large folders can take a while."))
                parca.append(_("Everything starts automatically when you log in."))
                self.bitti_sayfasi.set_description("\n\n".join(parca))
            self.git(len(self.sayfalar) - 1)
        arka_planda(lambda: servisleri_uygula(self.ayar), bitti)
