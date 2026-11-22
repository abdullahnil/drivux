"""Small pieces shared by the main window and the setup wizard."""

import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from . import ortak  # noqa: E402
from .ceviri import _  # noqa: E402

# (setting value, English label — translated where it is shown)
GDOCS_SECENEKLERI = [
    ("baglanti", "Show as shortcuts that open in the browser"),
    ("gizle", "Don't show"),
]


def arka_planda(is_, bitince=None):
    """Runs is_() in a thread and hands the result (or the exception) to bitince() on the main loop."""
    def calis():
        try:
            sonuc = is_()
        except Exception as e:  # noqa: BLE001 — carry the error to the UI
            sonuc = e
        if bitince:
            GLib.idle_add(bitince, sonuc)
    threading.Thread(target=calis, daemon=True).start()


def klasor_ekle(pencere: Gtk.Window, mevcut: list[dict], baglama_noktasi: str, eklendi):
    """Lets the user pick a folder and its name on Drive, then calls eklendi({"yerel","uzak","hazir"})."""
    def secildi(dialog, sonuc):
        try:
            dosya = dialog.select_folder_finish(sonuc)
        except GLib.Error:
            return
        yerel = Path(dosya.get_path())
        if any(ortak.yol(k["yerel"]) == yerel for k in mevcut):
            _uyari(pencere, _("This folder is already in the list."))
            return
        nokta = ortak.yol(baglama_noktasi)
        if yerel in (Path.home(), Path("/")) or yerel == nokta or nokta in yerel.parents:
            _uyari(pencere, _("This folder can't be synced. Don't pick your home folder itself or a folder "
                              "inside the Drive disk; pick a folder inside your home folder instead."))
            return

        giris = Gtk.Entry(text=yerel.name, activates_default=True)
        dlg = Adw.AlertDialog(
            heading=_("Folder name on Drive"),
            body=_("Which Google Drive folder should {path} be synced with?\n"
                   "It is created if it doesn't exist; if it does, the contents are merged (nothing is deleted).\n"
                   "Use / for subfolders, e.g. Documents/School").format(path=ortak.kisalt(yerel)))
        dlg.set_extra_child(giris)
        dlg.add_response("iptal", _("Cancel"))
        dlg.add_response("ekle", _("Add"))
        dlg.set_response_appearance("ekle", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("ekle")

        def yanit(_d, r):
            ad = giris.get_text().strip().strip("/")
            if r == "ekle" and ad:
                eklendi({"yerel": ortak.kisalt(yerel), "uzak": ad, "hazir": False})
        dlg.connect("response", yanit)
        dlg.present(pencere)

    Gtk.FileDialog(title=_("Choose a folder to sync")).select_folder(pencere, None, secildi)


def _uyari(pencere, metin):
    dlg = Adw.AlertDialog(heading=_("That didn't work"), body=metin)
    dlg.add_response("tamam", _("OK"))
    dlg.present(pencere)


def servisleri_uygula(ayar: dict) -> list[str]:
    """Enables/starts or disables the systemd user services to match the settings. Returns error messages."""
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
