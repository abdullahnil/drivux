"""rclone'un güncel sürümünü resmi siteden indirip uygulamanın kendi klasörüne kurar.

Sistem paket yöneticisine ve sudo'ya gerek yoktur. Dağıtımların depolarındaki rclone
çoğu zaman eşitleme için gereken özellikleri içermeyecek kadar eskidir
(ör. Ubuntu 24.04'te 1.60). İndirilen dosya rclone'un yayımladığı SHA256 özetiyle
doğrulanır.
"""

import hashlib
import io
import os
import platform
import zipfile
from urllib.request import Request, urlopen

from . import ortak
from .ceviri import _

TABAN = "https://downloads.rclone.org"
MIMARI = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64",
          "armv7l": "arm-v7", "armv6l": "arm-v6", "i686": "386", "i386": "386"}


def _indir(url: str, ilerleme=None) -> bytes:
    istek = Request(url, headers={"User-Agent": f"drivux/{ortak.SURUM}"})
    with urlopen(istek, timeout=60) as yanit:
        toplam = int(yanit.headers.get("Content-Length") or 0)
        tampon = io.BytesIO()
        while parca := yanit.read(256 * 1024):
            tampon.write(parca)
            if ilerleme and toplam:
                ilerleme(tampon.tell() / toplam)
    return tampon.getvalue()


def guncel_surum() -> str:
    """Örn. 'v1.76.0'."""
    return _indir(f"{TABAN}/version.txt").decode().split()[-1]


def kur(ilerleme=None, durum=None) -> str:
    """rclone'u indirip kurar, kurulan dosyanın yolunu döndürür.

    ilerleme(oran: float) ve durum(metin: str) isteğe bağlı geri çağırmalardır.
    """
    durum = durum or (lambda _m: None)
    mimari = MIMARI.get(platform.machine())
    if not mimari:
        raise RuntimeError(_("This processor architecture is not supported: {arch}").format(arch=platform.machine()))

    durum(_("Finding the latest version…"))
    surum = guncel_surum()
    ad = f"rclone-{surum}-linux-{mimari}"

    durum(_("Downloading checksums…"))
    ozetler = _indir(f"{TABAN}/{surum}/SHA256SUMS").decode()
    beklenen = next((s.split()[0] for s in ozetler.splitlines() if s.strip().endswith(f"{ad}.zip")), None)
    if not beklenen:
        raise RuntimeError(_("No checksum found for {file}").format(file=f"{ad}.zip"))

    durum(_("Downloading rclone {version}…").format(version=surum))
    veri = _indir(f"{TABAN}/{surum}/{ad}.zip", ilerleme)

    durum(_("Verifying the download…"))
    if hashlib.sha256(veri).hexdigest() != beklenen:
        raise RuntimeError(_("The download could not be verified (SHA256 mismatch). Please try again."))

    durum(_("Installing…"))
    hedef = ortak.OZEL_RCLONE
    hedef.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(veri)) as z:
        icerik = z.read(f"{ad}/rclone")
    gecici = hedef.with_suffix(".yeni")
    gecici.write_bytes(icerik)
    gecici.chmod(0o755)
    os.replace(gecici, hedef)

    ortak.rclone_yolu(yenile=True)
    durum(_("rclone {version} installed").format(version=surum))
    return str(hedef)
