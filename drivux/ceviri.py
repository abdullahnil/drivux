"""Interface translations.

The source language is English. Translations live in dictionaries keyed by the
English text. The language follows the system locale; it can be overridden with
the "dil" setting ("auto", "en", "tr").

Usage:  from .ceviri import _
        _("Sync now")
        _("{n} folders").format(n=3)
"""

import json
import os

from .ceviri_tr import TR

DILLER = {"en": None, "tr": TR}
DIL_ADLARI = [("auto", "Automatic"), ("en", "English"), ("tr", "Türkçe")]


def _sistem_dili() -> str:
    for degisken in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        deger = os.environ.get(degisken, "")
        for parca in deger.split(":"):
            kod = parca.split("_")[0].split(".")[0].lower()
            if kod in DILLER:
                return kod
            if kod and kod not in ("c", "posix"):
                break
    return "en"


def _ayardaki_dil() -> str:
    # ortak.py'yi içe aktarmadan (döngüsel bağımlılık olmasın diye) ayar dosyasını oku
    yol = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                       "drivux", "ayar.json")
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f).get("dil", "auto")
    except (OSError, ValueError):
        return "auto"


def etkin_dil() -> str:
    secim = _ayardaki_dil()
    return secim if secim in DILLER else _sistem_dili()


_sozluk = DILLER[etkin_dil()]


def _(metin: str) -> str:
    if _sozluk is None:
        return metin
    return _sozluk.get(metin, metin)


def _n(tekil: str, cogul: str, n: int) -> str:
    """Sayıya göre tekil/çoğul seçer (Türkçede ikisi aynı çevrilir)."""
    return _(tekil if n == 1 else cogul)
