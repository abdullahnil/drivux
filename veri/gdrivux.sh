#!/bin/sh
# G-Drivux başlatıcısı
PYTHONPATH="@PYDIR@${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m gdrivux "$@"
