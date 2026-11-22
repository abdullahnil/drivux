#!/bin/sh
# Drivux başlatıcısı
PYTHONPATH="@PYDIR@${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m drivux "$@"
