#!/usr/bin/env python3
"""Checks that every interface string has a Turkish translation with the same placeholders.

    python3 paketleme/ceviri-kontrol.py
"""
import ast
import pathlib
import re
import sys

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
from drivux.bilesenler import GDOCS_SECENEKLERI  # noqa: E402
from drivux.ceviri import DIL_ADLARI  # noqa: E402
from drivux.ceviri_tr import TR  # noqa: E402

metinler = set()
for dosya in (KOK / "drivux").glob("*.py"):
    for dugum in ast.walk(ast.parse(dosya.read_text(encoding="utf-8"))):
        if isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Name) and dugum.func.id in ("_", "_n"):
            for arg in dugum.args[: 1 if dugum.func.id == "_" else 2]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    metinler.add(arg.value)
metinler |= {e for _k, e in GDOCS_SECENEKLERI} | {e for _k, e in DIL_ADLARI}

def yer(s):
    return set(re.findall(r"{\w+}", s))

eksik = sorted(m for m in metinler if m not in TR)
fazla = sorted(k for k in TR if k not in metinler)
bozuk = sorted(k for k, v in TR.items() if not v or yer(k) != yer(v))
for baslik, liste in (("Missing translation", eksik), ("Unused translation", fazla), ("Bad translation", bozuk)):
    for m in liste:
        print(f"{baslik}: {m!r}")
print(f"{len(metinler)} strings, {len(TR)} Turkish translations")
sys.exit(1 if eksik or bozuk else 0)
