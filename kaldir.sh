#!/bin/bash
# kur.sh ile kurulan G-Drivux'u kaldırır. Bilgisayardaki ve Drive'daki dosyalara dokunmaz.
# (.rpm / .deb paketiyle kurduysan paket yöneticinle kaldır.)
set -eu
sor() { local c; read -r -p "$1 [e/H] " c </dev/tty || c=; [[ "$c" =~ ^[eEyY] ]]; }

sor "G-Drivux kaldırılsın mı?" || { echo "Vazgeçildi."; exit 0; }

systemctl --user disable --now gdrivux.service gdrivux-disk.service 2>/dev/null || true
rm -f "$HOME"/.config/systemd/user/gdrivux{,-disk}.service
systemctl --user daemon-reload
rm -rf "$HOME/.local/share/gdrivux/gdrivux"
rm -f "$HOME/.local/bin/gdrivux" \
      "$HOME/.local/share/applications/io.github.abdullahnil.GDrivux.desktop" \
      "$HOME/.local/share/icons/hicolor/scalable/apps/io.github.abdullahnil.GDrivux.svg"
sed -i '/ Google Drive$/d' "$HOME/.config/gtk-3.0/bookmarks" 2>/dev/null || true

if sor "Uygulamanın indirdiği rclone, ayarlar ve durum kayıtları da silinsin mi?"; then
    rm -rf "$HOME/.local/share/gdrivux" \
           "${XDG_CONFIG_HOME:-$HOME/.config}/gdrivux" "${XDG_STATE_HOME:-$HOME/.local/state}/gdrivux"
fi
echo "Kaldırıldı. Dosyaların yerinde duruyor; Google bağlantın (rclone ayarı) da korunuyor."
