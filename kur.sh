#!/bin/bash
# G-Drivux — kaynaktan kurulum (yalnızca bu kullanıcı için, ~/.local altına)
#
#   ./kur.sh
#
# Sistem paketlerini (GTK4, libadwaita, FUSE) dağıtımına göre kurar, uygulamayı
# ~/.local altına yerleştirir ve kurulum sihirbazını açar. rclone'un kurulması,
# Google hesabının bağlanması ve diğer bütün sorular sihirbazdadır.
# Güncellemek için de aynı betiği çalıştır; ayarların korunur.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

PYDIR="$HOME/.local/share/gdrivux"
BIN="$HOME/.local/bin"
UYG="$HOME/.local/share/applications"
SIMGE="$HOME/.local/share/icons/hicolor/scalable/apps"
SYSTEMD="$HOME/.config/systemd/user"
KIMLIK="io.github.abdullahnil.GDrivux"

if [ -t 1 ]; then Y=$'\e[1;32m'; S=$'\e[1;33m'; K=$'\e[1;31m'; M=$'\e[1;34m'; N=$'\e[0m'; else Y=; S=; K=; M=; N=; fi
adim()  { echo; echo "${M}==>${N} $*"; }
bilgi() { echo "    $*"; }
hata()  { echo "${K}HATA:${N} $*" >&2; exit 1; }

[ "$EUID" -eq 0 ] && hata "sudo ile değil, normal kullanıcı olarak çalıştır. Gerekirse şifre sorulur."
echo "${Y}G-Drivux — kurulum${N}"

# ---------- 1. sistem paketleri ----------
adim "1/3 Gerekli sistem paketleri"
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
    if   command -v dnf    >/dev/null; then sudo dnf install -y python3-gobject gtk4 libadwaita fuse3 libnotify
    elif command -v apt-get >/dev/null; then sudo apt-get update && sudo apt-get install -y python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 fuse3 libnotify-bin
    elif command -v pacman >/dev/null; then sudo pacman -S --needed --noconfirm python-gobject gtk4 libadwaita fuse3 libnotify
    elif command -v zypper >/dev/null; then sudo zypper install -y python3-gobject typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 fuse3 libnotify-tools
    else hata "Paket yöneticin tanınmadı. Elle kur: Python GObject, GTK 4, libadwaita (>= 1.5), fuse3, notify-send"
    fi
    gi_tamam || hata "libadwaita 1.5 veya daha yenisi gerekli. Dağıtımın bunu sunmuyor olabilir (ör. Ubuntu 24.04 ve sonrası, Fedora 40 ve sonrası çalışır)."
else
    bilgi "Hepsi kurulu."
fi

# ---------- 2. uygulama ----------
adim "2/3 Uygulama kuruluyor (~/.local)"
mkdir -p "$PYDIR" "$BIN" "$UYG" "$SIMGE" "$SYSTEMD"
rm -rf "$PYDIR/gdrivux"
cp -r gdrivux "$PYDIR/"
find "$PYDIR" -name __pycache__ -prune -exec rm -rf {} +
sed "s|@PYDIR@|$PYDIR|" veri/gdrivux.sh > "$BIN/gdrivux"
chmod 755 "$BIN/gdrivux"
sed "s|^Exec=gdrivux|Exec=$BIN/gdrivux|" veri/gdrivux.desktop > "$UYG/$KIMLIK.desktop"
install -m 644 "veri/$KIMLIK.svg" "$SIMGE/"
for s in systemd/*.service; do
    sed "s|@BINDIR@|$BIN|g" "$s" > "$SYSTEMD/$(basename "$s")"
done
systemctl --user daemon-reload
update-desktop-database "$UYG" 2>/dev/null || true
gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
bilgi "Uygulama menüsünde: G-Drivux"

# 1.1 ve öncesi "Drive Bağlantı" kurulumundan geçiş
if PYTHONPATH="$PYDIR" python3 -c 'import sys; from gdrivux import ortak; sys.exit(0 if ortak.eski_surumden_tasi() else 1)'; then
    bilgi "Eski \"Drive Bağlantı\" kurulumu bulundu; ayarlar G-Drivux'a taşındı."
fi
[ -d "$HOME/.local/share/drive-baglanti/bin" ] && [ ! -x "$PYDIR/bin/rclone" ] || rm -rf "$HOME/.local/share/drive-baglanti"
rm -f "$HOME/.local/bin/drive-baglanti" \
      "$HOME/.local/share/applications/io.github.abdullahnil.DriveBaglanti.desktop" \
      "$HOME/.local/share/icons/hicolor/scalable/apps/io.github.abdullahnil.DriveBaglanti.svg"

# 1.0 öncesi elle kurulmuş gdrive-senkr eşitlemesini uygulamaya taşı
if [ -f "$SYSTEMD/gdrive-senkr.service" ]; then
    eski_yerel="$(grep -oP 'bisync \K\S+' "$SYSTEMD/gdrive-senkr.service" | sed "s|%h|$HOME|")"
    eski_uzak="$(grep -oP 'bisync \S+ \S+?:\K\S+' "$SYSTEMD/gdrive-senkr.service")"
    PYTHONPATH="$PYDIR" python3 - "$eski_yerel" "$eski_uzak" <<'PY'
import sys
from gdrivux import ortak
yerel, uzak = ortak.kisalt(sys.argv[1]), sys.argv[2]
a = ortak.ayar_oku()
if yerel and uzak and not any(k["yerel"] == yerel for k in a["klasorler"]):
    a["klasorler"].append({"yerel": yerel, "uzak": uzak, "hazir": True})
    ortak.ayar_yaz(a)
    print(f"    Eski eşitleme uygulamaya taşındı: {yerel} <-> {uzak}")
PY
    systemctl --user disable --now gdrive-senkr.timer gdrive-senkr.path 2>/dev/null || true
    rm -f "$SYSTEMD"/gdrive-senkr.{service,timer,path}
fi

# ---------- 3. sihirbaz / güncelleme ----------
adim "3/3 Son adım"
tamam="$(PYTHONPATH="$PYDIR" python3 -c 'from gdrivux import ortak; print(int(ortak.ayar_oku()["kurulum_tamam"] and bool(ortak.rclone_yolu())))')"
if [ "$tamam" = 1 ]; then
    PYTHONPATH="$PYDIR" python3 -c 'from gdrivux import ortak, bilesenler; print("\n".join(bilesenler.servisleri_uygula(ortak.ayar_oku())) or "    Servisler güncellendi ve yeniden başlatıldı.")'
    echo; echo "${Y}Güncelleme tamamlandı.${N}"
elif [ -n "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ]; then
    bilgi "Kurulum sihirbazı açılıyor; rclone, Google hesabı ve diğer ayarlar orada."
    (setsid "$BIN/gdrivux" >/dev/null 2>&1 &)
    echo; echo "${Y}Kurulum tamamlandı.${N} Sihirbazdaki adımları izle."
else
    echo; echo "${Y}Kurulum tamamlandı.${N} Masaüstünde \"G-Drivux\"yı açıp sihirbazı tamamla."
fi
