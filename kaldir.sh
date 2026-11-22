#!/bin/bash
# Removes a Drivux install made with kur.sh. Your files on the computer and on Drive are not touched.
# (If you installed the .rpm / .deb package, remove it with your package manager instead.)
set -eu
case "${LANGUAGE:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in tr*) TR=1 ;; *) TR=0 ;; esac
t() { if [ "$TR" = 1 ]; then printf '%s' "$2"; else printf '%s' "$1"; fi; }
sor() { local c; read -r -p "$1 [$(t y/N e/H)] " c </dev/tty || c=; [[ "$c" =~ ^[eEyY] ]]; }

sor "$(t "Remove Drivux?" "Drivux kaldırılsın mı?")" || { t "Cancelled." "Vazgeçildi."; echo; exit 0; }

systemctl --user disable --now drivux.service drivux-disk.service 2>/dev/null || true
rm -f "$HOME"/.config/systemd/user/drivux{,-disk}.service
systemctl --user daemon-reload
rm -rf "$HOME/.local/share/drivux/drivux"
rm -f "$HOME/.local/bin/drivux" \
      "$HOME/.local/share/applications/io.github.abdullahnil.Drivux.desktop" \
      "$HOME/.local/share/icons/hicolor/scalable/apps/io.github.abdullahnil.Drivux.svg"
sed -i '/ Google Drive$/d' "$HOME/.config/gtk-3.0/bookmarks" 2>/dev/null || true

if sor "$(t "Also delete the rclone Drivux downloaded, the settings and the status files?" \
            "Drivux'un indirdiği rclone, ayarlar ve durum dosyaları da silinsin mi?")"; then
    rm -rf "$HOME/.local/share/drivux" \
           "${XDG_CONFIG_HOME:-$HOME/.config}/drivux" "${XDG_STATE_HOME:-$HOME/.local/state}/drivux"
fi
t "Drivux removed. Your files are where they were, and your Google connection (rclone config) is kept." \
  "Drivux kaldırıldı. Dosyaların yerinde duruyor; Google bağlantın (rclone ayarı) da korunuyor."
echo
