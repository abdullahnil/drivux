"""Top bar (tray) icon.

Runs as a separate process because tray icons (StatusNotifierItem via AppIndicator)
need GTK 3, while the app uses GTK 4. Started from the session's autostart entry
and by the app; it exits on its own if the tray icon is turned off in Settings.

On GNOME the "AppIndicator and KStatusNotifierItem Support" extension is needed
(Ubuntu ships it; on Fedora: gnome-shell-extension-appindicator).
"""

import fcntl
import os
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
except (ValueError, ImportError):
    try:
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3 as AppIndicator  # noqa: E402
    except (ValueError, ImportError):
        AppIndicator = None

from . import guncelle, ortak  # noqa: E402
from .bicim import gecen_sure  # noqa: E402
from .ceviri import _, _n  # noqa: E402

SIMGE = ortak.UYGULAMA_KIMLIGI + "-symbolic"
UYARI_SIMGESI = "dialog-warning-symbolic"


def _drivux(*args):
    """Starts drivux (the same launcher this process came from) without waiting."""
    komut = [sys.executable, "-P", "-m", "drivux", *args]
    subprocess.Popen(komut, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Tepsi:
    def __init__(self):
        self.gosterge = AppIndicator.Indicator.new(
            "drivux", SIMGE, AppIndicator.IndicatorCategory.APPLICATION_STATUS)
        # Works for ~/.local installs too, where the icon may not be in the system theme
        for yol in (os.path.join(GLib.get_user_data_dir(), "icons"), "/usr/share/icons"):
            if os.path.exists(os.path.join(yol, "hicolor/symbolic/apps", SIMGE + ".svg")):
                self.gosterge.set_icon_theme_path(os.path.join(yol, "hicolor/symbolic/apps"))
                break
        self.gosterge.set_title("Drivux")
        self.gosterge.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.gosterge.set_attention_icon_full(UYARI_SIMGESI, _("Sync has a problem"))

        menu = Gtk.Menu()
        self.durum = Gtk.MenuItem(label=_("Checking…"), sensitive=False)
        self.alt_durum = Gtk.MenuItem(label="", sensitive=False)
        menu.append(self.durum)
        menu.append(self.alt_durum)
        self.guncelleme = Gtk.MenuItem(label="")
        self.guncelleme.connect("activate", lambda *_a: _drivux("update"))
        menu.append(self.guncelleme)
        menu.append(Gtk.SeparatorMenuItem())
        ac = Gtk.MenuItem(label=_("Open Drivux"))
        ac.connect("activate", lambda *_a: _drivux())
        menu.append(ac)
        self.drive_ac = Gtk.MenuItem(label=_("Open Google Drive"))
        self.drive_ac.connect("activate", lambda *_a: Gtk.show_uri_on_window(
            None, GLib.filename_to_uri(str(ortak.yol(ortak.ayar_oku()["baglama_noktasi"]))), 0))
        menu.append(self.drive_ac)
        self.esitle = Gtk.MenuItem(label=_("Sync now"))
        self.esitle.connect("activate", lambda *_a: ortak.servise_sinyal("USR1"))
        menu.append(self.esitle)
        menu.append(Gtk.SeparatorMenuItem())
        gizle = Gtk.MenuItem(label=_("Hide this icon"))
        gizle.connect("activate", lambda *_a: self.gizle())
        menu.append(gizle)
        menu.show_all()
        self.guncelleme.set_visible(False)
        self.gosterge.set_menu(menu)
        self.gosterge.set_secondary_activate_target(ac)   # middle click opens Drivux

        self.yenile()
        GLib.timeout_add_seconds(3, self.yenile)

    def yenile(self):
        # After an update the files on disk are newer than this process: start again with them
        if guncelle.kurulu_surum() != ortak.SURUM:
            os.execv(sys.executable, [sys.executable, "-P", "-m", "drivux", "tray"])
        yeni = guncelle.bekleyen_surum()
        self.guncelleme.set_visible(bool(yeni))
        if yeni:
            self.guncelleme.set_label(_("Update available: Drivux {version}").format(version=yeni))
        ayar = ortak.ayar_oku()
        if not ayar.get("tepsi", True):
            Gtk.main_quit()
            return GLib.SOURCE_REMOVE
        durum = ortak.durum_oku()
        servis = ortak.servis_aktif(ortak.SERVIS)
        hatalar = [d for d in durum.get("klasorler", {}).values() if d.get("sonuc") == "hata"]
        if not servis:
            baslik, alt, sorun = _("Sync service is not running"), _("Open Drivux to fix it"), True
        elif durum.get("calisiyor"):
            baslik, alt, sorun = _("Syncing…"), _("Copying changes"), False
        elif hatalar:
            baslik = _("Sync has a problem")
            alt = _n("{n} folder has an error", "{n} folders have errors", len(hatalar)).format(n=len(hatalar))
            sorun = True
        else:
            baslik = _("Everything is up to date")
            alt = _("Last sync: {when}").format(when=gecen_sure(durum.get("son_esitleme")))
            sorun = False
        self.durum.set_label(baslik)
        self.alt_durum.set_label(alt)
        self.esitle.set_sensitive(servis and not durum.get("calisiyor"))
        self.drive_ac.set_visible(bool(ayar.get("disk", True)) and ortak.disk_bagli(ayar))
        self.gosterge.set_status(AppIndicator.IndicatorStatus.ATTENTION if sorun
                                 else AppIndicator.IndicatorStatus.ACTIVE)
        self.gosterge.set_title(f"Drivux — {baslik}")
        return GLib.SOURCE_CONTINUE

    def gizle(self):
        ayar = ortak.ayar_oku()
        ayar["tepsi"] = False
        ortak.ayar_yaz(ayar)
        Gtk.main_quit()


def main() -> int:
    if AppIndicator is None:
        print("Tray icon needs the AppIndicator library "
              "(Fedora: libappindicator-gtk3, Ubuntu/Debian: gir1.2-ayatanaappindicator3-0.1).", file=sys.stderr)
        return 1
    ayar = ortak.ayar_oku()
    if not ayar.get("tepsi", True) or not ayar.get("kurulum_tamam"):
        return 0
    # only one tray icon per session
    ortak.DURUM_KLASORU.mkdir(parents=True, exist_ok=True)
    kilit = open(ortak.DURUM_KLASORU / "tepsi.kilit", "w")
    try:
        fcntl.flock(kilit, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0
    Tepsi()
    Gtk.main()
    return 0
