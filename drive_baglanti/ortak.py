"""Uygulama ile arka plan servisinin ortak kullandığı ayar ve durum işlemleri."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

UYGULAMA_KIMLIGI = "io.github.abdullahnil.DriveBaglanti"
SERVIS = "drive-baglanti.service"
DISK_SERVISI = "drive-baglanti-disk.service"

_config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
_state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")

AYAR_DOSYASI = _config / "drive-baglanti" / "ayar.json"
DURUM_KLASORU = _state / "drive-baglanti"
DURUM_DOSYASI = DURUM_KLASORU / "durum.json"
ISTEK_DOSYASI = DURUM_KLASORU / "istek.json"

VARSAYILAN_AYAR = {
    "uzak": "gdrive",                     # rclone bağlantısının adı
    "baglama_noktasi": "~/Google Drive",  # diskin bağlanacağı klasör
    "aralik_dk": 5,                       # düzenli eşitleme aralığı
    "onbellek_gb": 10,                    # disk için yerel önbellek sınırı
    "en_fazla_silme": 50,                 # bundan fazla silmede eşitleme durur
    "klasorler": [],                      # [{"yerel": "~/...", "uzak": "klasor", "hazir": bool}]
}


def yol(p: str) -> Path:
    return Path(os.path.expanduser(p))


def kisalt(p: Path | str) -> str:
    """Ev klasörünü ~ ile gösterir."""
    s = str(p)
    ev = str(Path.home())
    return "~" + s[len(ev):] if s == ev or s.startswith(ev + "/") else s


def _atomik_yaz(dosya: Path, veri) -> None:
    dosya.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=dosya.parent, delete=False, encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)
        gecici = f.name
    os.replace(gecici, dosya)


def _oku(dosya: Path, varsayilan):
    try:
        return json.loads(dosya.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return varsayilan


def ayar_oku() -> dict:
    ayar = dict(VARSAYILAN_AYAR)
    ayar.update(_oku(AYAR_DOSYASI, {}))
    return ayar


def ayar_yaz(ayar: dict) -> None:
    _atomik_yaz(AYAR_DOSYASI, ayar)


def durum_oku() -> dict:
    return _oku(DURUM_DOSYASI, {})


def durum_yaz(durum: dict) -> None:
    _atomik_yaz(DURUM_DOSYASI, durum)


def istek_ekle(**alanlar) -> None:
    """Servise istek bırakır (ör. zorla eşitleme) ve onu uyandırır."""
    istek = _oku(ISTEK_DOSYASI, {})
    for k, v in alanlar.items():
        if isinstance(v, list):
            istek[k] = sorted(set(istek.get(k, [])) | set(v))
        else:
            istek[k] = v
    _atomik_yaz(ISTEK_DOSYASI, istek)
    servise_sinyal("USR1")


def istek_al() -> dict:
    istek = _oku(ISTEK_DOSYASI, {})
    ISTEK_DOSYASI.unlink(missing_ok=True)
    return istek


def systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True)


def servis_aktif(servis: str) -> bool:
    return systemctl("is-active", "--quiet", servis).returncode == 0


def servise_sinyal(sinyal: str) -> None:
    """USR1: hemen eşitle, HUP: ayarları yeniden oku."""
    systemctl("kill", "--kill-whom=main", "-s", sinyal, SERVIS)


def disk_bagli(ayar: dict | None = None) -> bool:
    ayar = ayar or ayar_oku()
    return os.path.ismount(yol(ayar["baglama_noktasi"]))
