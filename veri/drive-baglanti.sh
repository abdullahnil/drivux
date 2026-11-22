#!/bin/sh
# Drive Bağlantı başlatıcısı
PYTHONPATH="@PYDIR@${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m drive_baglanti "$@"
