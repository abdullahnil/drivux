#!/bin/bash
# Drivux — install from source (for the current user only, under ~/.local)
#
#   ./kur.sh
#
# Installs the system packages Drivux needs (GTK 4, libadwaita, FUSE) with your
# distribution's package manager, puts the app under ~/.local and opens the
# setup wizard. Installing rclone, connecting your Google account and every
# other question are handled by the wizard.
# Run it again to update; your settings are kept.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

PYDIR="$HOME/.local/share/drivux"
BIN="$HOME/.local/bin"
UYG="$HOME/.local/share/applications"
SIMGE="$HOME/.local/share/icons/hicolor/scalable/apps"
SEMBOL="$HOME/.local/share/icons/hicolor/symbolic/apps"
OTOBASLAT="$HOME/.config/autostart"
SYSTEMD="$HOME/.config/systemd/user"
KIMLIK="io.github.abdullahnil.Drivux"

# Messages follow the system language: t "English" "Türkçe"
case "${LANGUAGE:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in tr*) TR=1 ;; *) TR=0 ;; esac
t() { if [ "$TR" = 1 ]; then printf '%s' "$2"; else printf '%s' "$1"; fi; }

if [ -t 1 ]; then Y=$'\e[1;32m'; K=$'\e[1;31m'; M=$'\e[1;34m'; N=$'\e[0m'; else Y=; K=; M=; N=; fi
adim()  { echo; echo "${M}==>${N} $*"; }
bilgi() { echo "    $*"; }
hata()  { echo "${K}$(t ERROR HATA):${N} $*" >&2; exit 1; }

[ "$EUID" -eq 0 ] && hata "$(t "Run this as your normal user, not with sudo. You'll be asked for a password if needed." \
                               "sudo ile değil, normal kullanıcı olarak çalıştır. Gerekirse şifre sorulur.")"
echo "${Y}$(t "Drivux — setup" "Drivux — kurulum")${N}"

# ---------- 1. system packages ----------
adim "$(t "1/3 Required system packages" "1/3 Gerekli sistem paketleri")"
gi_tamam() {
    python3 - <<'PY' 2>/dev/null
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Adw
assert (Adw.get_major_version(), Adw.get_minor_version()) >= (1, 5)
PY
}
eksik_var=false
command -v python3 >/dev/null && gi_tamam || eksik_var=true
command -v fusermount3 >/dev/null || eksik_var=true
command -v notify-send >/dev/null || eksik_var=true
if $eksik_var; then
    if   command -v dnf     >/dev/null; then sudo dnf install -y python3-gobject gtk4 libadwaita fuse3 libnotify
    elif command -v apt-get >/dev/null; then sudo apt-get update && sudo apt-get install -y python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 fuse3 libnotify-bin
    elif command -v pacman  >/dev/null; then sudo pacman -S --needed --noconfirm python-gobject gtk4 libadwaita fuse3 libnotify
    elif command -v zypper  >/dev/null; then sudo zypper install -y python3-gobject typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 fuse3 libnotify-tools
    else hata "$(t "Unknown package manager. Install these yourself: Python GObject, GTK 4, libadwaita (>= 1.5), fuse3, notify-send" \
                   "Paket yöneticin tanınmadı. Bunları elle kur: Python GObject, GTK 4, libadwaita (>= 1.5), fuse3, notify-send")"
    fi
    gi_tamam || hata "$(t "libadwaita 1.5 or newer is required; your distribution may not provide it (Fedora 40+, Ubuntu 24.04+ and Debian 13+ work)." \
                          "libadwaita 1.5 ya da daha yenisi gerekli; dağıtımın bunu sunmuyor olabilir (Fedora 40+, Ubuntu 24.04+ ve Debian 13+ çalışır).")"
else
    bilgi "$(t "All installed." "Hepsi kurulu.")"
fi
# Top bar icon (optional): AppIndicator library for GTK 3
if ! python3 -c 'import gi
for n in ("AyatanaAppIndicator3", "AppIndicator3"):
    try:
        gi.require_version(n, "0.1"); break
    except ValueError: pass
else: raise SystemExit(1)' 2>/dev/null; then
    bilgi "$(t "Installing the library for the top bar icon" "Üst çubuk simgesi için kütüphane kuruluyor")"
    if   command -v dnf     >/dev/null; then sudo dnf install -y libappindicator-gtk3 || true
    elif command -v apt-get >/dev/null; then sudo apt-get install -y gir1.2-ayatanaappindicator3-0.1 || true
    elif command -v pacman  >/dev/null; then sudo pacman -S --needed --noconfirm libayatana-appindicator || true
    elif command -v zypper  >/dev/null; then sudo zypper install -y typelib-1_0-AyatanaAppIndicator3-0_1 || true
    fi
fi
if [ "${XDG_CURRENT_DESKTOP:-}" != "${XDG_CURRENT_DESKTOP/GNOME/}" ] && \
   ! gnome-extensions list --enabled 2>/dev/null | grep -q appindicator; then
    bilgi "$(t "Tip: on GNOME, the top bar icon needs the \"AppIndicator and KStatusNotifierItem Support\" extension." \
               "İpucu: GNOME'da üst çubuk simgesi için \"AppIndicator and KStatusNotifierItem Support\" eklentisi gerekir.")"
fi

# ---------- 2. app ----------
adim "$(t "2/3 Installing Drivux (~/.local)" "2/3 Drivux kuruluyor (~/.local)")"
mkdir -p "$PYDIR" "$BIN" "$UYG" "$SIMGE" "$SEMBOL" "$OTOBASLAT" "$SYSTEMD"
rm -rf "$PYDIR/drivux"
cp -r drivux "$PYDIR/"
find "$PYDIR" -name __pycache__ -prune -exec rm -rf {} +
sed "s|@PYDIR@|$PYDIR|" veri/drivux.sh > "$BIN/drivux"
chmod 755 "$BIN/drivux"
sed "s|^Exec=drivux|Exec=$BIN/drivux|" veri/drivux.desktop > "$UYG/$KIMLIK.desktop"
install -m 644 "veri/$KIMLIK.svg" "$SIMGE/"
install -m 644 "veri/$KIMLIK-symbolic.svg" "$SEMBOL/"
sed "s|^Exec=drivux|Exec=$BIN/drivux|" veri/drivux-tray.desktop > "$OTOBASLAT/$KIMLIK.tray.desktop"
for s in systemd/*.service; do
    sed "s|@BINDIR@|$BIN|g" "$s" > "$SYSTEMD/$(basename "$s")"
done
systemctl --user daemon-reload

# Migrate installs made under the old names (Drive Bağlantı 1.1, G-Drivux 1.2)
if PYTHONPATH="$PYDIR" python3 -c 'import sys; from drivux import ortak; sys.exit(0 if ortak.eski_surumden_tasi() else 1)'; then
    bilgi "$(t "Found an older install (Drive Bağlantı / G-Drivux); settings moved to Drivux." \
               "Eski bir kurulum bulundu (Drive Bağlantı / G-Drivux); ayarlar Drivux'a taşındı.")"
fi
for eski in drive-baglanti gdrivux; do
    rm -f "$BIN/$eski"
    rm -rf "$HOME/.local/share/$eski"
done
rm -f "$UYG"/io.github.abdullahnil.{DriveBaglanti,GDrivux}.desktop \
      "$SIMGE"/io.github.abdullahnil.{DriveBaglanti,GDrivux}.svg

update-desktop-database "$UYG" 2>/dev/null || true
gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
bilgi "$(t "Drivux is in your app menu." "Drivux uygulama menüsünde.")"

# ---------- 3. wizard / update ----------
adim "$(t "3/3 Last step" "3/3 Son adım")"
tamam="$(PYTHONPATH="$PYDIR" python3 -c 'from drivux import ortak; print(int(ortak.ayar_oku()["kurulum_tamam"] and bool(ortak.rclone_yolu())))')"
if [ "$tamam" = 1 ]; then
    hatalar="$(PYTHONPATH="$PYDIR" python3 -c 'from drivux import ortak, bilesenler; print("\n".join(bilesenler.servisleri_uygula(ortak.ayar_oku())))')"
    [ -n "$hatalar" ] && echo "$hatalar" || bilgi "$(t "Services updated and restarted." "Servisler güncellendi ve yeniden başlatıldı.")"
    echo; echo "${Y}$(t "Update complete." "Güncelleme tamamlandı.")${N}"
elif [ -n "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ]; then
    bilgi "$(t "Opening the setup wizard; rclone, your Google account and the other settings are set there." \
               "Kurulum sihirbazı açılıyor; rclone, Google hesabın ve diğer ayarlar orada yapılır.")"
    (setsid "$BIN/drivux" >/dev/null 2>&1 &)
    echo; echo "${Y}$(t "Installed." "Kuruldu.")${N} $(t "Follow the steps in the wizard." "Sihirbazdaki adımları izle.")"
else
    echo; echo "${Y}$(t "Installed." "Kuruldu.")${N} $(t "Open Drivux on your desktop to finish setup." "Kurulumu bitirmek için masaüstünde Drivux'u aç.")"
fi
