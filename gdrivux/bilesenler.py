"""Arayüz ile kurulum sihirbazının ortak kullandığı küçük parçalar."""

import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from . import ortak  # noqa: E402

GDOCS_SECENEKLERI = [
    ("baglanti", "Tarayıcıda açılan kısayol olarak göster"),
    ("gizle", "Gösterme"),
]


def arka_planda(is_, bitince=None):
    """is_()'i ayrı iş parçacığında çalıştırır, sonucu ana döngüde bitince()'ye verir."""
    def calis():
        try:
            sonuc = is_()
        except Exception as e:  # noqa: BLE001 — hatayı arayüze taşı
            sonuc = e
        if bitince:
            GLib.idle_add(bitince, sonuc)
    threading.Thread(target=calis, daemon=True).start()


def klasor_ekle(pencere: Gtk.Window, mevcut: list[dict], baglama_noktasi: str, eklendi):
    """Klasör seçtirir, Drive'daki adını sorar; eklendi({"yerel","uzak","hazir"}) çağırır."""
    def secildi(dialog, sonuc):
        try:
            dosya = dialog.select_folder_finish(sonuc)
        except GLib.Error:
            return
        yerel = Path(dosya.get_path())
        if any(ortak.yol(k["yerel"]) == yerel for k in mevcut):
            _uyari(pencere, "Bu klasör zaten listede.")
            return
        nokta = ortak.yol(baglama_noktasi)
        if yerel in (Path.home(), Path("/")) or yerel == nokta or nokta in yerel.parents:
            _uyari(pencere, "Bu klasör eşitlenemez. Ev klasörünün kendisini ya da Drive diskinin "
                            "içini seçme; içinde bir alt klasör seç.")
            return

        giris = Gtk.Entry(text=yerel.name, activates_default=True)
        dlg = Adw.AlertDialog(
            heading="Drive'daki klasör adı",
            body=f"{ortak.kisalt(yerel)} klasörü Google Drive'da hangi klasörle eşitlensin?\n"
                 "Drive'da yoksa oluşturulur; varsa içerikleri birleştirilir (hiçbir şey silinmez).\n"
                 "Alt klasör için / kullan, ör. Belgeler/Okul")
        dlg.set_extra_child(giris)
        dlg.add_response("iptal", "İptal")
        dlg.add_response("ekle", "Ekle")
        dlg.set_response_appearance("ekle", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("ekle")

        def yanit(_d, r):
            ad = giris.get_text().strip().strip("/")
            if r == "ekle" and ad:
                eklendi({"yerel": ortak.kisalt(yerel), "uzak": ad, "hazir": False})
        dlg.connect("response", yanit)
        dlg.present(pencere)

    Gtk.FileDialog(title="Eşitlenecek klasörü seç").select_folder(pencere, None, secildi)


def _uyari(pencere, metin):
    dlg = Adw.AlertDialog(heading="Olmadı", body=metin)
    dlg.add_response("tamam", "Tamam")
    dlg.present(pencere)


def servisleri_uygula(ayar: dict) -> list[str]:
    """Ayara göre systemd kullanıcı servislerini açar/kapatır. Hata mesajlarını döndürür."""
    hatalar = []
    ortak.systemctl("daemon-reload")
    for servis, acik in ((ortak.SERVIS, True), (ortak.DISK_SERVISI, ayar.get("disk", True))):
        if acik:
            ortak.systemctl("enable", servis)
            r = ortak.systemctl("restart", servis)
        else:
            r = ortak.systemctl("disable", "--now", servis)
        if r.returncode != 0:
            hatalar.append(f"{servis}: {r.stderr.strip()}")
    if ayar.get("disk", True):
        ortak.yer_imi_ekle(ortak.yol(ayar["baglama_noktasi"]))
    return hatalar
