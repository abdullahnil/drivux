"""Checking for and installing Drivux updates (no GTK here).

Updates come from the GitHub releases of the project. How an update is installed
depends on how Drivux was installed:

- .rpm package → the new .rpm is downloaded and installed with dnf (via pkexec)
- .deb package → the new .deb is downloaded and installed with apt (via pkexec)
- from source  → the release's source code is downloaded and its kur.sh is run
"""

import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

from . import ortak
from .ceviri import _

DEPO = "abdullahnil/drivux"
API = f"https://api.github.com/repos/{DEPO}/releases/latest"
DURUM = ortak.DURUM_KLASORU / "guncelleme.json"
KONTROL_ARALIGI = 24 * 3600            # automatic check at most once a day
PAKET_KOKU = Path(__file__).resolve().parent


def surum_demeti(s: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", s)[:3])


def _istek(url: str, kabul: str = "application/vnd.github+json"):
    return urlopen(Request(url, headers={"User-Agent": f"drivux/{ortak.SURUM}", "Accept": kabul}), timeout=30)


def son_surum() -> dict:
    """Latest release: {"surum", "notlar", "sayfa", "kaynak", "paketler": {"rpm"|"deb": {"ad","url","boyut"}}}."""
    with _istek(API) as yanit:
        veri = json.load(yanit)
    paketler = {}
    for a in veri.get("assets", []):
        tur = "rpm" if a["name"].endswith(".rpm") else "deb" if a["name"].endswith(".deb") else None
        if tur:
            paketler[tur] = {"ad": a["name"], "url": a["browser_download_url"], "boyut": a.get("size", 0)}
    return {
        "surum": veri["tag_name"].lstrip("v"),
        "notlar": veri.get("body") or "",
        "sayfa": veri.get("html_url", f"https://github.com/{DEPO}/releases"),
        "kaynak": f"https://github.com/{DEPO}/archive/refs/tags/{veri['tag_name']}.tar.gz",
        "paketler": paketler,
    }


def yeni_mi(surum: str) -> bool:
    return surum_demeti(surum) > surum_demeti(ortak.SURUM)


# ---------- remembered state (so the tray and the app can show it) ----------
def durum_oku() -> dict:
    try:
        return json.loads(DURUM.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _durum_yaz(**alanlar) -> None:
    d = durum_oku()
    d.update(alanlar)
    DURUM.parent.mkdir(parents=True, exist_ok=True)
    DURUM.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def kontrol_et(zorla: bool = False) -> dict | None:
    """Checks GitHub (at most once a day unless zorla). Returns the release if it is newer, else None."""
    d = durum_oku()
    if not zorla and time.time() - d.get("son_kontrol", 0) < KONTROL_ARALIGI:
        bilgi = d.get("bilgi")
        return bilgi if bilgi and yeni_mi(bilgi["surum"]) else None
    bilgi = son_surum()
    _durum_yaz(son_kontrol=time.time(), bilgi=bilgi)
    return bilgi if yeni_mi(bilgi["surum"]) else None


def bekleyen_surum() -> str | None:
    """A newer version found by the last check, without contacting GitHub."""
    bilgi = durum_oku().get("bilgi")
    return bilgi["surum"] if bilgi and yeni_mi(bilgi["surum"]) else None


# ---------- install type ----------
def kurulum_turu() -> str:
    """'rpm', 'deb' or 'kaynak' (installed with kur.sh under ~/.local)."""
    dosya = str(PAKET_KOKU / "ortak.py")
    if not dosya.startswith("/usr/"):
        return "kaynak"
    if shutil.which("rpm") and subprocess.run(["rpm", "-qf", dosya], capture_output=True).returncode == 0:
        return "rpm"
    if shutil.which("dpkg") and subprocess.run(["dpkg", "-S", dosya], capture_output=True).returncode == 0:
        return "deb"
    return "bilinmiyor"


# ---------- install ----------
def _indir(url: str, hedef: Path, ilerleme=None, beklenen: int = 0) -> None:
    with _istek(url, kabul="*/*") as yanit, open(hedef, "wb") as f:
        toplam = int(yanit.headers.get("Content-Length") or beklenen or 0)
        alinan = 0
        while parca := yanit.read(256 * 1024):
            f.write(parca)
            alinan += len(parca)
            if ilerleme and toplam:
                ilerleme(min(1.0, alinan / toplam))
    if beklenen and hedef.stat().st_size != beklenen:
        raise RuntimeError(_("The download is incomplete. Please try again."))


def kur(bilgi: dict, ilerleme=None, durum=None) -> None:
    """Downloads and installs the release described by bilgi. Raises RuntimeError on failure."""
    durum = durum or (lambda _m: None)
    tur = kurulum_turu()
    is_klasoru = Path(tempfile.mkdtemp(prefix="drivux-guncelleme-"))
    try:
        if tur in ("rpm", "deb"):
            paket = bilgi["paketler"].get(tur)
            if not paket:
                raise RuntimeError(_("This release has no .{kind} package.").format(kind=tur))
            dosya = is_klasoru / paket["ad"]
            durum(_("Downloading {file}…").format(file=paket["ad"]))
            _indir(paket["url"], dosya, ilerleme, paket.get("boyut", 0))
            os.chmod(is_klasoru, 0o755)      # the package manager runs as root and must read it
            os.chmod(dosya, 0o644)
            durum(_("Installing… (you'll be asked for your password)"))
            komut = (["pkexec", "dnf", "install", "-y", str(dosya)] if tur == "rpm"
                     else ["pkexec", "apt-get", "install", "-y", str(dosya)])
            r = subprocess.run(komut, capture_output=True, text=True)
            if r.returncode == 126:
                raise RuntimeError(_("Installation was cancelled."))
            if r.returncode != 0:
                cikti = (r.stderr or r.stdout).strip().splitlines()
                raise RuntimeError(cikti[-1] if cikti else _("The package manager reported an error."))
        elif tur == "kaynak":
            arsiv = is_klasoru / "kaynak.tar.gz"
            durum(_("Downloading Drivux {version}…").format(version=bilgi["surum"]))
            _indir(bilgi["kaynak"], arsiv, ilerleme)
            durum(_("Installing…"))
            with tarfile.open(arsiv) as t:
                t.extractall(is_klasoru / "kaynak", filter="data")
            kok = next((is_klasoru / "kaynak").iterdir())
            ortam = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
            r = subprocess.run(["bash", str(kok / "kur.sh")], cwd=kok, capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, env=ortam)
            if r.returncode != 0:
                son = (r.stderr or r.stdout).strip().splitlines()
                raise RuntimeError(son[-1] if son else _("kur.sh reported an error."))
        else:
            raise RuntimeError(_("Couldn't tell how Drivux was installed; download the new version from the "
                                 "releases page."))
        durum(_("Restarting the services…"))
        servisleri_yeniden_baslat()
        _durum_yaz(bilgi=bilgi, kuruldu=bilgi["surum"])
    finally:
        shutil.rmtree(is_klasoru, ignore_errors=True)


def kurulu_surum() -> str:
    """Version of the Drivux files on disk (may be newer than the running process after an update)."""
    m = re.search(r'^SURUM = "([^"]+)"', (PAKET_KOKU / "ortak.py").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else ortak.SURUM


def servisleri_yeniden_baslat() -> None:
    ortak.systemctl("daemon-reload")
    for servis in (ortak.SERVIS, ortak.DISK_SERVISI):
        if ortak.servis_aktif(servis):
            ortak.systemctl("restart", servis)
