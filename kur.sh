#!/bin/bash
# Drive Bağlantı kurulumu
#   - Gerekli paketleri kurar (rclone, GTK4, libadwaita, FUSE)
#   - Google Drive bağlantısı yoksa tarayıcıda Google girişini açar
#   - Uygulamayı, menü kısayolunu ve arka plan servislerini kurar
#   - Google Drive'ı ~/Google Drive klasörüne disk olarak bağlar
# Güncellemek için de aynı betiği tekrar çalıştırman yeterli; ayarların korunur.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

PAYLASIM="$HOME/.local/share/drive-baglanti"
BIN="$HOME/.local/bin"
UYG="$HOME/.local/share/applications"
SYSTEMD="$HOME/.config/systemd/user"
AYAR_KLASORU="${XDG_CONFIG_HOME:-$HOME/.config}/drive-baglanti"
AYAR="$AYAR_KLASORU/ayar.json"
KIMLIK="io.github.abdullahnil.DriveBaglanti"

if [ -t 1 ]; then Y=$'\e[1;32m'; S=$'\e[1;33m'; K=$'\e[1;31m'; M=$'\e[1;34m'; N=$'\e[0m'; else Y=; S=; K=; M=; N=; fi
adim()  { echo; echo "${M}==>${N} $*"; }
bilgi() { echo "    $*"; }
hata()  { echo "${K}HATA:${N} $*" >&2; exit 1; }

[ "$EUID" -eq 0 ] && hata "sudo ile değil, normal kullanıcı olarak çalıştır."
echo "${Y}Drive Bağlantı — kurulum${N}"

# ---------- 1. paketler ----------
adim "1/5 Gerekli paketler kontrol ediliyor"
eksik=()
command -v rclone >/dev/null || eksik+=(rclone)
command -v fusermount3 >/dev/null || eksik+=(fuse3)
command -v notify-send >/dev/null || eksik+=(libnotify)
python3 -c 'import gi; gi.require_version("Adw","1"); gi.require_version("Gtk","4.0"); from gi.repository import Adw, Gtk' \
    2>/dev/null || eksik+=(python3-gobject gtk4 libadwaita)
if [ ${#eksik[@]} -gt 0 ]; then
    bilgi "Kuruluyor: ${eksik[*]}"
    sudo dnf install -y "${eksik[@]}"
else
    bilgi "Hepsi kurulu."
fi

# ---------- 2. Google Drive bağlantısı ----------
adim "2/5 Google Drive bağlantısı"
mapfile -t uzaklar < <(rclone listremotes --type drive 2>/dev/null | sed 's/:$//')
if [ -f "$AYAR" ]; then
    UZAK="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("uzak","gdrive"))' "$AYAR")"
elif [ ${#uzaklar[@]} -eq 1 ]; then
    UZAK="${uzaklar[0]}"
elif [ ${#uzaklar[@]} -gt 1 ]; then
    echo "    Birden fazla Google Drive bağlantısı var:"
    for i in "${!uzaklar[@]}"; do echo "      $((i + 1))) ${uzaklar[$i]}"; done
    read -r -p "    Hangisi kullanılsın? [1] " s </dev/tty || s=
    UZAK="${uzaklar[$(( ${s:-1} - 1 ))]}"
else
    UZAK="gdrive"
fi
if printf '%s\n' "${uzaklar[@]}" | grep -qx "$UZAK"; then
    bilgi "Kullanılan bağlantı: $UZAK"
else
    bilgi "Tarayıcıda Google girişi açılıyor. Hesabını seçip rclone'a izin ver..."
    rclone config create "$UZAK" drive scope=drive >/dev/null
    bilgi "Bağlantı oluşturuldu: $UZAK"
fi

# ---------- 3. dosyalar ----------
adim "3/5 Uygulama kuruluyor"
mkdir -p "$PAYLASIM" "$BIN" "$UYG" "$SYSTEMD"
rm -rf "$PAYLASIM/drive_baglanti"
cp -r drive_baglanti "$PAYLASIM/"
find "$PAYLASIM" -name __pycache__ -prune -exec rm -rf {} +
install -m 755 veri/drive-baglanti.sh "$BIN/drive-baglanti"
install -m 644 veri/drive-baglanti.desktop "$UYG/$KIMLIK.desktop"
install -m 644 systemd/drive-baglanti.service systemd/drive-baglanti-disk.service "$SYSTEMD/"
update-desktop-database "$UYG" 2>/dev/null || true
bilgi "Uygulama menüsünde: Drive Bağlantı"

# ---------- 4. ayarlar ----------
adim "4/5 Ayarlar"
mkdir -p "$AYAR_KLASORU"
if [ ! -f "$AYAR" ]; then
    python3 - "$AYAR" "$UZAK" <<'PY'
import json, sys
json.dump({"uzak": sys.argv[2], "baglama_noktasi": "~/Google Drive", "aralik_dk": 5,
           "onbellek_gb": 10, "en_fazla_silme": 50, "klasorler": []},
          open(sys.argv[1], "w"), ensure_ascii=False, indent=2)
PY
    bilgi "Oluşturuldu: $AYAR"
else
    bilgi "Mevcut ayarlar korunuyor."
fi

# Elle kurulmuş eski gdrive-senkr eşitlemesini bu uygulamaya taşı
if [ -f "$SYSTEMD/gdrive-senkr.service" ]; then
    eski_yerel="$(grep -oP 'bisync \K\S+' "$SYSTEMD/gdrive-senkr.service" | sed "s|%h|$HOME|")"
    eski_uzak="$(grep -oP 'bisync \S+ \S+?:\K\S+' "$SYSTEMD/gdrive-senkr.service")"
    if [ -n "$eski_yerel" ] && [ -n "$eski_uzak" ]; then
        bilgi "Eski eşitleme bulundu ($eski_yerel ↔ $eski_uzak), uygulamaya taşınıyor."
        python3 - "$AYAR" "$eski_yerel" "$eski_uzak" "$HOME" <<'PY'
import json, sys
dosya, yerel, uzak, ev = sys.argv[1:]
if yerel.startswith(ev + "/"):
    yerel = "~" + yerel[len(ev):]
a = json.load(open(dosya))
if not any(k["yerel"] == yerel for k in a["klasorler"]):
    a["klasorler"].append({"yerel": yerel, "uzak": uzak, "hazir": True})
json.dump(a, open(dosya, "w"), ensure_ascii=False, indent=2)
PY
    fi
    systemctl --user disable --now gdrive-senkr.timer gdrive-senkr.path 2>/dev/null || true
    rm -f "$SYSTEMD"/gdrive-senkr.{service,timer,path}
fi

# Dosyalar'ın kenar çubuğuna yer imi
YER_IMI="$HOME/.config/gtk-3.0/bookmarks"
mkdir -p "$(dirname "$YER_IMI")"
NOKTA="$(python3 -c 'import json,os,sys; print(os.path.expanduser(json.load(open(sys.argv[1]))["baglama_noktasi"]))' "$AYAR")"
URI="$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).as_uri())' "$NOKTA")"
grep -q "^$URI " "$YER_IMI" 2>/dev/null || echo "$URI Google Drive" >> "$YER_IMI"

# ---------- 5. servisler ----------
adim "5/5 Servisler başlatılıyor"
systemctl --user daemon-reload
systemctl --user enable drive-baglanti.service drive-baglanti-disk.service 2>/dev/null
systemctl --user restart drive-baglanti.service
systemctl --user restart drive-baglanti-disk.service
for _ in $(seq 20); do mountpoint -q "$NOKTA" && break; sleep 0.5; done
if mountpoint -q "$NOKTA"; then
    bilgi "Google Drive bağlandı: $NOKTA"
else
    echo "    ${S}Disk henüz bağlanmadı; ayrıntı için: journalctl --user -u drive-baglanti-disk${N}"
fi

echo
echo "${Y}Kurulum tamamlandı!${N}"
cat <<SON

  • Uygulama menüsünden "Drive Bağlantı"yı aç: durum, klasör ekleme/çıkarma ve ayarlar orada.
  • Google Drive, Dosyalar'ın kenar çubuğunda "Google Drive" olarak görünür.
  • Eşitleme ve disk, oturum açınca kendiliğinden başlar.
SON
