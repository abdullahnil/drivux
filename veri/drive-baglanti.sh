#!/bin/sh
# Drive Bağlantı başlatıcısı
PYTHONPATH="$HOME/.local/share/drive-baglanti${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m drive_baglanti "$@"
