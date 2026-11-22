"""İlk açılış kurulum sihirbazı.

Adımlar: hoş geldin → rclone → Google hesabı → disk → klasörler → özet → bitti
"""

import re
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import ortak, rclone_kur  # noqa: E402
from .bilesenler import GDOCS_SECENEKLERI, arka_planda, klasor_ekle, servisleri_uygula  # noqa: E402

CLIENT_ID_REHBERI = "https://rclone.org/drive/#making-your-own-client-id"


class Sihirbaz(Adw.ApplicationWindow):
    def __init__(self, uyg, bitince):
        super().__init__(application=uyg, title="G-Drivux — Kurulum",
                         default_width=620, default_height=680)
        self.bitince = bitince
        self.ayar = ortak.ayar_oku()
        self.hesap_hazir = False
        self.giris_sureci: subprocess.Popen | None = None
        self.mesgul = False

        self.toast = Adw.ToastOverlay()
        gorunum = Adw.ToolbarView()
        self.baslik = Adw.WindowTitle(title="Kurulum")
        ust = Adw.HeaderBar(title_widget=self.baslik)
        gorunum.add_top_bar(ust)

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
        self.geri = Gtk.Button(label="Geri")
        self.geri.connect("clicked", lambda *_: self.git(self.sira - 1))
        self.ileri = Gtk.Button(label="İleri", css_classes=["suggested-action"])
        self.ileri.connect("clicked", lambda *_: self.ileri_bas())
        alt.set_start_widget(self.geri)
        alt.set_end_widget(self.ileri)
        gorunum.add_bottom_bar(alt)

        self.toast.set_child(gorunum)
        self.set_content(self.toast)
        self.connect("close-request", self._kapaniyor)
        self.sira = 0
        self.git(0)

    # ---------- gezinme ----------
    def git(self, sira: int):
        sira = max(0, min(sira, len(self.sayfalar) - 1))
        self.yigin.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT if sira > self.sira
                                       else Gtk.StackTransitionType.SLIDE_RIGHT)
        self.sira = sira
        ad = self.sayfalar[sira][0]
        self.yigin.set_visible_child_name(ad)
        adim_sayisi = len(self.sayfalar) - 2
        self.baslik.set_subtitle(f"Adım {sira} / {adim_sayisi}" if 0 < sira <= adim_sayisi else "")
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
        etiket = {"hosgeldin": "Başla", "ozet": "Kur", "bitti": "Uygulamayı aç"}.get(ad, "İleri")
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

    def _kapaniyor(self, *_):
        if self.giris_sureci and self.giris_sureci.poll() is None:
            self.giris_sureci.terminate()
        return False

    def bildir(self, metin):
        self.toast.add_toast(Adw.Toast(title=metin, timeout=4))

    # ---------- sayfalar ----------
    def sayfa_hosgeldin(self):
        return Adw.StatusPage(
            icon_name=ortak.UYGULAMA_KIMLIGI,
            title="G-Drivux'a hoş geldin",
            description="Birkaç adımda Google Drive'ı bu bilgisayara bağlayacağız:\n\n"
                        "• Drive'ın tamamı Dosyalar'da bir disk gibi görünecek\n"
                        "• Seçtiğin klasörler bilgisayarla Drive arasında iki yönlü eşitlenecek\n\n"
                        "Gereken her şey bu sihirbaz içinden kurulur.")

    def sayfa_rclone(self):
        sayfa = Adw.PreferencesPage()
        grup = Adw.PreferencesGroup(
            title="rclone",
            description="G-Drivux, Google Drive ile konuşmak için rclone adlı açık kaynak aracı "
                        f"kullanır. En az {ortak.surum_metni(ortak.EN_DUSUK_RCLONE)} gerekir.")
        self.rclone_satiri = Adw.ActionRow(title="Kontrol ediliyor…")
        self.rclone_simgesi = Gtk.Image(icon_size=Gtk.IconSize.LARGE)
        self.rclone_satiri.add_prefix(self.rclone_simgesi)
        grup.add(self.rclone_satiri)
        self.rclone_dugmesi = Gtk.Button(label="rclone'u indir ve kur", halign=Gtk.Align.CENTER,
                                         css_classes=["suggested-action", "pill"], margin_top=18)
        self.rclone_dugmesi.connect("clicked", lambda *_: self.rclone_indir())
        self.rclone_ilerleme = Gtk.ProgressBar(visible=False, margin_top=18, show_text=True)
        aciklama = Gtk.Label(
            label="rclone resmi sitesinden (downloads.rclone.org) indirilir, doğrulanır ve yalnızca "
                  "bu kullanıcı için kurulur. Yönetici şifresi gerekmez.",
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
            title="Google hesabı",
            description="Tarayıcıda Google girişi açılacak. Hesabını seçip izin vermen yeterli; "
                        "şifren bu uygulamaya hiç gelmez.")
        self.ad_girisi = Adw.EntryRow(title="Bağlantı adı", text=self.ayar["uzak"])
        self.ad_girisi.connect("changed", lambda *_: self.hesap_kontrol())
        grup.add(self.ad_girisi)
        self.hesap_satiri = Adw.ActionRow(title="")
        self.hesap_simgesi = Gtk.Image()
        self.hesap_satiri.add_prefix(self.hesap_simgesi)
        grup.add(self.hesap_satiri)
        sayfa.add(grup)

        gelismis = Adw.PreferencesGroup()
        self.client_genisleyen = Adw.ExpanderRow(
            title="Kendi Google client ID'ni kullan (önerilir)",
            subtitle="rclone'un ortak kimliği kapatılıyor; kendi kimliğinle bağlantın kesintisiz çalışır",
            show_enable_switch=True, enable_expansion=False)
        self.client_id = Adw.EntryRow(title="Client ID")
        self.client_secret = Adw.PasswordEntryRow(title="Client secret")
        rehber = Adw.ActionRow(title="Nasıl oluşturulur?", subtitle="rclone rehberini tarayıcıda aç",
                               activatable=True)
        rehber.add_suffix(Gtk.Image(icon_name="web-browser-symbolic"))
        rehber.connect("activated", lambda *_: Gio.AppInfo.launch_default_for_uri(CLIENT_ID_REHBERI, None))
        for r in (self.client_id, self.client_secret, rehber):
            self.client_genisleyen.add_row(r)
        gelismis.add(self.client_genisleyen)
        sayfa.add(gelismis)

        dugme_grubu = Adw.PreferencesGroup()
        kutu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, halign=Gtk.Align.CENTER)
        self.giris_dugmesi = Gtk.Button(label="Google ile giriş yap", css_classes=["suggested-action", "pill"])
        self.giris_dugmesi.connect("clicked", lambda *_: self.google_giris())
        self.giris_bekleme = Gtk.Box(spacing=8, visible=False, halign=Gtk.Align.CENTER)
        self.giris_bekleme.append(Gtk.Spinner(spinning=True))
        self.giris_bekleme.append(Gtk.Label(label="Tarayıcıda girişi tamamla…"))
        iptal = Gtk.Button(label="İptal", css_classes=["flat"])
        iptal.connect("clicked", lambda *_: self.giris_iptal())
        self.giris_bekleme.append(iptal)
        kutu.append(self.giris_dugmesi)
        kutu.append(self.giris_bekleme)
        dugme_grubu.add(kutu)
        sayfa.add(dugme_grubu)
        return sayfa

    def sayfa_disk(self):
        sayfa = Adw.PreferencesPage()
        grup = Adw.PreferencesGroup(
            title="Google Drive diski",
            description="Drive'ın tamamı Dosyalar'da bir disk gibi görünür. Dosyalar açıldıkça indirilir; "
                        "bilgisayarda yalnızca önbellek kadar yer kaplar.")
        self.disk_anahtari = Adw.SwitchRow(title="Drive'ı disk olarak bağla", active=self.ayar["disk"])
        self.disk_anahtari.connect("notify::active", lambda *_: self._disk_secenekleri())
        grup.add(self.disk_anahtari)

        self.nokta_girisi = Adw.EntryRow(title="Bağlanacağı klasör", text=self.ayar["baglama_noktasi"])
        self.nokta_girisi.connect("changed", lambda *_: self.dugmeleri_guncelle())
        sec = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER, css_classes=["flat"],
                         tooltip_text="Klasör seç")
        sec.connect("clicked", lambda *_: self._nokta_sec())
        self.nokta_girisi.add_suffix(sec)
        grup.add(self.nokta_girisi)

        self.gdocs_secimi = Adw.ComboRow(
            title="Google Docs, E-Tablolar, Slaytlar",
            subtitle="Kısayola çift tıklayınca dosya tarayıcıda Google'ın kendi düzenleyicisinde açılır",
            model=Gtk.StringList.new([e for _, e in GDOCS_SECENEKLERI]))
        self.gdocs_secimi.set_selected(next(i for i, (k, _) in enumerate(GDOCS_SECENEKLERI)
                                            if k == self.ayar["gdocs"]))
        grup.add(self.gdocs_secimi)

        self.onbellek = Adw.SpinRow.new_with_range(1, 500, 1)
        self.onbellek.set_title("Önbellek sınırı (GB)")
        self.onbellek.set_subtitle("Diskten açılan dosyalar bilgisayarda en fazla bu kadar yer kaplar")
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
        Gtk.FileDialog(title="Drive'ın bağlanacağı klasör").select_folder(self, None, secildi)

    def sayfa_klasorler(self):
        sayfa = Adw.PreferencesPage()
        self.klasor_grubu = Adw.PreferencesGroup(
            title="Eşitlenecek klasörler (isteğe bağlı)",
            description="Bu klasörler bilgisayarda da durur, internet olmadan da açılır ve değişiklikler "
                        "iki yönde aktarılır. Şimdi eklemezsen sonra uygulamadan ekleyebilirsin.")
        ekle = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Klasör ekle",
                          valign=Gtk.Align.CENTER, css_classes=["flat"])
        ekle.connect("clicked", lambda *_: klasor_ekle(self, self.ayar["klasorler"],
                                                       self.nokta_girisi.get_text(), self._klasor_eklendi))
        self.klasor_grubu.set_header_suffix(ekle)
        self.klasor_satirlari = []
        sayfa.add(self.klasor_grubu)

        ayar_grubu = Adw.PreferencesGroup()
        self.aralik = Adw.SpinRow.new_with_range(1, 120, 1)
        self.aralik.set_title("Eşitleme aralığı (dakika)")
        self.aralik.set_subtitle("Klasörde değişiklik olunca ayrıca birkaç saniye içinde eşitlenir")
        self.aralik.set_value(self.ayar["aralik_dk"])
        ayar_grubu.add(self.aralik)
        sayfa.add(ayar_grubu)
        self._klasorleri_ciz()
        return sayfa

    def _klasor_eklendi(self, k):
        self.ayar["klasorler"].append(k)
        self._klasorleri_ciz()

    def _klasorleri_ciz(self):
        for s in self.klasor_satirlari:
            self.klasor_grubu.remove(s)
        self.klasor_satirlari = []
        if not self.ayar["klasorler"]:
            s = Adw.ActionRow(title="Henüz klasör yok", subtitle="Eklemek için + düğmesine bas")
            self.klasor_grubu.add(s)
            self.klasor_satirlari.append(s)
        for k in self.ayar["klasorler"]:
            s = Adw.ActionRow(title=GLib.markup_escape_text(ortak.kisalt(ortak.yol(k["yerel"]))),
                              subtitle=GLib.markup_escape_text(f"Drive: {k['uzak']}"))
            s.add_prefix(Gtk.Image(icon_name="folder-symbolic"))
            sil = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER, css_classes=["flat"])
            sil.connect("clicked", lambda *_a, k=k: (self.ayar["klasorler"].remove(k), self._klasorleri_ciz()))
            s.add_suffix(sil)
            self.klasor_grubu.add(s)
            self.klasor_satirlari.append(s)

    def sayfa_ozet(self):
        sayfa = Adw.PreferencesPage()
        self.ozet_grubu = Adw.PreferencesGroup(title="Özet",
                                               description="\"Kur\"a basınca ayarlar kaydedilir ve servisler "
                                                           "başlatılır. Hepsini sonra değiştirebilirsin.")
        self.ozet_satirlari = []
        sayfa.add(self.ozet_grubu)
        return sayfa

    def ozeti_doldur(self):
        for s in self.ozet_satirlari:
            self.ozet_grubu.remove(s)
        a = self.ayar
        satirlar = [
            ("Google hesabı", f"rclone bağlantısı: {a['uzak']}"),
            ("Drive diski", f"{a['baglama_noktasi']} · önbellek {a['onbellek_gb']} GB · Google Docs: "
                            f"{dict(GDOCS_SECENEKLERI)[a['gdocs']].lower()}" if a["disk"] else "bağlanmayacak"),
            ("Eşitlenen klasörler", "\n".join(f"{k['yerel']}  ↔  Drive: {k['uzak']}" for k in a["klasorler"])
             or "yok (sonra eklenebilir)"),
            ("Eşitleme aralığı", f"{a['aralik_dk']} dakika"),
            ("Otomatik başlatma", "Oturum açınca eşitleme ve disk kendiliğinden başlar"),
        ]
        self.ozet_satirlari = []
        for baslik, alt in satirlar:
            s = Adw.ActionRow(title=baslik, subtitle=GLib.markup_escape_text(alt), subtitle_selectable=True)
            s.set_subtitle_lines(0)
            self.ozet_grubu.add(s)
            self.ozet_satirlari.append(s)

    def sayfa_bitti(self):
        self.bitti_sayfasi = Adw.StatusPage(icon_name="emblem-ok-symbolic", title="Hazır!")
        return self.bitti_sayfasi

    # ---------- rclone adımı ----------
    def rclone_kontrol(self):
        def is_():
            return ortak.rclone_yolu(yenile=True), ortak.rclone_adaylari()

        def bitti(sonuc):
            yol, adaylar = sonuc
            if yol:
                surum = dict(adaylar).get(yol)
                self.rclone_simgesi.set_from_icon_name("emblem-ok-symbolic")
                self.rclone_satiri.set_title(f"rclone {ortak.surum_metni(surum)} hazır")
                self.rclone_satiri.set_subtitle(ortak.kisalt(yol))
                self.rclone_dugmesi.set_visible(False)
            else:
                eski = [f"{ortak.kisalt(y)} ({ortak.surum_metni(s)})" for y, s in adaylar]
                self.rclone_simgesi.set_from_icon_name("dialog-warning-symbolic")
                self.rclone_satiri.set_title("Uygun rclone bulunamadı" if not eski else "Kurulu rclone çok eski")
                self.rclone_satiri.set_subtitle("Bulunan: " + ", ".join(eski) if eski
                                                else "Aşağıdaki düğmeyle kurabilirsin")
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
                self.bildir(f"Kurulamadı: {sonuc}")
            else:
                self.rclone_ilerleme.set_fraction(1)
            self.rclone_kontrol()
        arka_planda(lambda: rclone_kur.kur(ilerleme, durum), bitti)

    # ---------- hesap adımı ----------
    def _ad(self) -> str:
        return self.ad_girisi.get_text().strip()

    def hesap_kontrol(self):
        ad = self._ad()
        self.hesap_hazir = False
        if not re.fullmatch(r"[A-Za-z0-9_-]+", ad or "-!"):
            self.hesap_simgesi.set_from_icon_name("dialog-warning-symbolic")
            self.hesap_satiri.set_title("Geçersiz ad")
            self.hesap_satiri.set_subtitle("Yalnızca harf, rakam, - ve _ kullan (Türkçe karakter olmadan)")
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
                self.hesap_satiri.set_title("Bu adla bir Google Drive bağlantısı zaten var")
                self.hesap_satiri.set_subtitle("Onu kullanabilirsin; başka hesap için farklı bir ad yaz")
                self.giris_dugmesi.set_visible(False)
            else:
                self.hesap_simgesi.set_from_icon_name("dialog-information-symbolic")
                self.hesap_satiri.set_title("Henüz bağlı değil")
                self.hesap_satiri.set_subtitle("Aşağıdaki düğmeyle Google hesabına bağlan")
                self.giris_dugmesi.set_visible(self.giris_sureci is None)
            self.dugmeleri_guncelle()
        arka_planda(ortak.gdrivuxlari, bitti)

    def google_giris(self):
        ad = self._ad()
        komut = ortak.rclone("config", "create", ad, "drive", "scope=drive")
        if self.client_genisleyen.get_enable_expansion():
            cid, sec = self.client_id.get_text().strip(), self.client_secret.get_text().strip()
            if not cid or not sec:
                self.bildir("Client ID ve secret'ı birlikte gir ya da bu seçeneği kapat")
                return
            komut += [f"client_id={cid}", f"client_secret={sec}"]
        self.giris_dugmesi.set_visible(False)
        self.giris_bekleme.set_visible(True)
        self.ad_girisi.set_sensitive(False)
        self.mesgul = True
        self.dugmeleri_guncelle()
        # rclone tarayıcıyı kendisi açar ve Google'dan gelen yanıtı yerel bir adreste bekler
        self.giris_sureci = subprocess.Popen(komut, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        surec = self.giris_sureci

        def bitti(sonuc):
            cikti, kod = sonuc
            self.giris_sureci = None
            self.mesgul = False
            self.giris_bekleme.set_visible(False)
            self.ad_girisi.set_sensitive(True)
            if kod == 0:
                self.ayar["uzak"] = ad
                self.bildir("Google hesabı bağlandı")
            elif kod > 0:
                son = [s for s in cikti.splitlines() if s.strip()][-1:] or ["bilinmeyen hata"]
                self.bildir(f"Giriş tamamlanamadı: {son[0][:120]}")
            self.hesap_kontrol()
        arka_planda(lambda: (surec.communicate()[0], surec.returncode), bitti)

    def giris_iptal(self):
        if self.giris_sureci:
            self.giris_sureci.terminate()

    # ---------- uygula ----------
    def uygula(self):
        self.mesgul = True
        self.dugmeleri_guncelle()
        self.ileri.set_label("Kuruluyor…")
        self.ayar["kurulum_tamam"] = True
        ortak.ayar_yaz(self.ayar)

        def bitti(hatalar):
            self.mesgul = False
            if isinstance(hatalar, Exception):
                hatalar = [str(hatalar)]
            if hatalar:
                self.bitti_sayfasi.set_icon_name("dialog-warning-symbolic")
                self.bitti_sayfasi.set_title("Kuruldu ama bazı servisler başlamadı")
                self.bitti_sayfasi.set_description("\n".join(hatalar))
            else:
                parca = []
                if self.ayar["disk"]:
                    parca.append(f"Google Drive, Dosyalar'da kenar çubuğunda \"Google Drive\" olarak görünüyor "
                                 f"({self.ayar['baglama_noktasi']}).")
                if self.ayar["klasorler"]:
                    parca.append("Klasörlerin ilk eşitlemesi başladı; büyük klasörlerde biraz sürebilir.")
                parca.append("Her şey oturum açınca kendiliğinden çalışır.")
                self.bitti_sayfasi.set_description("\n\n".join(parca))
            self.git(len(self.sayfalar) - 1)
        arka_planda(lambda: servisleri_uygula(self.ayar), bitti)
