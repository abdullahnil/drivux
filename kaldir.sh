#!/bin/bash
# kur.sh ile kurulan Drive Bağlantı'yı kaldırır. Bilgisayardaki ve Drive'daki dosyalara dokunmaz.
# (.rpm / .deb paketiyle kurduysan paket yöneticinle kaldır.)
set -eu
sor() { local c; read -r -p "$1 [e/H] " c </dev/tty || c=; [[ "$c" =~ ^[eEyY] ]]; }

sor "Drive Bağlantı kaldırılsın mı?" || { echo "Vazgeçildi."; exit 0; }

systemctl --user disable --now drive-baglanti.service drive-baglanti-disk.service 2>/dev/null || true
rm -f "$HOME"/.config/systemd/user/drive-baglanti{,-disk}.service
systemctl --user daemon-reload
rm -rf "$HOME/.local/share/drive-baglanti/drive_baglanti"
rm -f "$HOME/.local/bin/drive-baglanti" \
      "$HOME/.local/share/applications/io.github.abdullahnil.DriveBaglanti.desktop" \
      "$HOME/.local/share/icons/hicolor/scalable/apps/io.github.abdullahnil.DriveBaglanti.svg"
sed -i '/ Google Drive$/d' "$HOME/.config/gtk-3.0/bookmarks" 2>/dev/null || true

if sor "Uygulamanın indirdiği rclone, ayarlar ve durum kayıtları da silinsin mi?"; then
    rm -rf "$HOME/.local/share/drive-baglanti" \
           "${XDG_CONFIG_HOME:-$HOME/.config}/drive-baglanti" "${XDG_STATE_HOME:-$HOME/.local/state}/drive-baglanti"
fi
echo "Kaldırıldı. Dosyaların yerinde duruyor; Google bağlantın (rclone ayarı) da korunuyor."
