#!/usr/bin/env python3
"""Builds the Drivux website into _site/ (used by GitHub Pages and Cloudflare Pages).

    python3 site/build.py

- Puts the current version (SURUM in drivux/ortak.py) wherever the page says {{VERSION}}.
  The page also asks GitHub for the latest release when it loads, so it stays
  current even if the site isn't rebuilt after a release.
- Copies the app's own logo, so the site always uses the same logo as the app.

Only the Python standard library is needed.
"""

import re
import shutil
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
CIKTI = KOK / "_site"

surum = re.search(r'^SURUM = "([^"]+)"', (KOK / "drivux/ortak.py").read_text(encoding="utf-8"), re.M).group(1)

if CIKTI.exists():
    shutil.rmtree(CIKTI)
CIKTI.mkdir()

sayfa = (KOK / "site/index.html").read_text(encoding="utf-8").replace("{{VERSION}}", surum)
(CIKTI / "index.html").write_text(sayfa, encoding="utf-8")
shutil.copy(KOK / "veri/io.github.abdullahnil.Drivux.svg", CIKTI / "logo.svg")
shutil.copy(KOK / "docs/logo.png", CIKTI / "logo.png")
(CIKTI / ".nojekyll").write_text("")          # GitHub Pages: serve files as they are

print(f"Built _site/ for Drivux {surum}")
