"""Uygulama ile arka plan servisinin ortak kullandığı ayar ve durum işlemleri."""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

SURUM = "1.4.0"
EN_DUSUK_RCLONE = (1, 66, 0)   # bisync --resilient/--recover/--conflict-resolve için
UYGULAMA_KIMLIGI = "io.github.abdullahnil.Drivux"
SERVIS = "drivux.service"
DISK_SERVISI = "drivux-disk.service"

_config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
_state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
_data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")

OZEL_RCLONE = _data / "drivux" / "bin" / "rclone"   # uygulamanın kendi indirdiği rclone

AYAR_DOSYASI = _config / "drivux" / "ayar.json"
DURUM_KLASORU = _state / "drivux"
DURUM_DOSYASI = DURUM_KLASORU / "durum.json"
ISTEK_DOSYASI = DURUM_KLASORU / "istek.json"

VARSAYILAN_AYAR = {
    "uzak": "gdrive",                     # rclone bağlantısının adı
    "baglama_noktasi": "~/Google Drive",  # diskin bağlanacağı klasör
    "aralik_dk": 5,                       # düzenli eşitleme aralığı
    "onbellek_gb": 10,                    # disk için yerel önbellek sınırı
    "en_fazla_silme": 50,                 # bundan fazla silmede eşitleme durur
    "disk": True,                         # Drive disk olarak bağlansın mı
    "gdocs": "baglanti",                  # Google Docs: "baglanti" (tarayıcıda açılır) | "gizle"
    "klasorler": [],                      # [{"yerel": "~/...", "uzak": "klasor", "hazir": bool}]
    "tepsi": True,                        # üst çubukta (tepside) simge gösterilsin mi
    "kurulum_tamam": False,               # ilk açılış sihirbazı tamamlandı mı
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
    dosyadaki = _oku(AYAR_DOSYASI, {})
    if dosyadaki and "kurulum_tamam" not in dosyadaki:
        dosyadaki["kurulum_tamam"] = True   # 1.0 sürümünden kalan ayar: kurulum yapılmış
    ayar.update(dosyadaki)
    ayar["klasorler"] = [dict(k) for k in ayar["klasorler"]]
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
    nokta = yol(ayar["baglama_noktasi"])
    try:
        os.stat(nokta)
    except OSError:
        return False
    return os.path.ismount(nokta)


# ---------- rclone ----------
_rclone_onbellek: dict = {}


def rclone_surumu(yol: str | Path) -> tuple | None:
    try:
        r = subprocess.run([str(yol), "version"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"rclone v(\d+)\.(\d+)\.(\d+)", r.stdout)
    return tuple(int(x) for x in m.groups()) if m else None


def rclone_adaylari() -> list[tuple[str, tuple | None]]:
    """Bulunan tüm rclone'lar ve sürümleri (önce uygulamanınki)."""
    adaylar = [OZEL_RCLONE, shutil.which("rclone"), Path.home() / ".local/bin/rclone", "/usr/bin/rclone"]
    gorulen, sonuc = set(), []
    for a in adaylar:
        if not a or not Path(a).is_file():
            continue
        gercek = os.path.realpath(a)
        if gercek in gorulen:
            continue
        gorulen.add(gercek)
        sonuc.append((str(a), rclone_surumu(a)))
    return sonuc


def rclone_yolu(yenile: bool = False) -> str | None:
    """Yeterince yeni ilk rclone'un yolu; yoksa None."""
    if yenile or "yol" not in _rclone_onbellek:
        _rclone_onbellek["yol"] = next(
            (y for y, s in rclone_adaylari() if s and s >= EN_DUSUK_RCLONE), None)
    return _rclone_onbellek["yol"]


def rclone(*args: str) -> list[str]:
    return [rclone_yolu() or "rclone", *args]


def surum_metni(s: tuple | None) -> str:
    return "v" + ".".join(map(str, s)) if s else "bilinmiyor"


def drive_hesaplari() -> list[str]:
    r = subprocess.run(rclone("listremotes", "--type", "drive"), capture_output=True, text=True)
    return [x.rstrip(":") for x in r.stdout.split() if x.strip()]


def yer_imi_ekle(yol: Path, ad: str = "Google Drive") -> None:
    dosya = Path.home() / ".config/gtk-3.0/bookmarks"
    dosya.parent.mkdir(parents=True, exist_ok=True)
    satirlar = dosya.read_text().splitlines() if dosya.exists() else []
    uri = yol.as_uri()
    if not any(s.split(" ")[0] == uri for s in satirlar):
        satirlar.append(f"{uri} {ad}")
        dosya.write_text("\n".join(satirlar) + "\n")


# ---------- geçiş: eski adlarla yapılmış kurulumlar ----------
# 1.1 ve öncesi "Drive Bağlantı" (drive-baglanti), 1.2 "G-Drivux" (gdrivux)
ESKI_ADLAR = ["gdrivux", "drive-baglanti"]   # yeniden eskiye


def eski_surumden_tasi() -> bool:
    """Eski adlarla kurulmuş sürümlerin ayar, durum ve rclone'unu yeni adlara taşır.

    Eski kullanıcı servislerini kapatır. Bir şey yapıldıysa True döner.
    """
    tasindi = False
    for eski_ad in ESKI_ADLAR:
        for eski, yeni in ((_config / eski_ad, AYAR_DOSYASI.parent),
                           (_state / eski_ad, DURUM_KLASORU),
                           (_data / eski_ad / "bin", OZEL_RCLONE.parent)):
            if eski.is_dir() and not yeni.exists():
                shutil.copytree(eski, yeni, symlinks=True)
                tasindi = True
        birimler = [f"{eski_ad}.service", f"{eski_ad}-disk.service"]
        if any(systemctl("is-enabled", "--quiet", b).returncode == 0 or servis_aktif(b) for b in birimler):
            systemctl("disable", "--now", *birimler)
            tasindi = True
        for b in birimler:
            (_config / "systemd" / "user" / b).unlink(missing_ok=True)
    if tasindi:
        _rclone_onbellek.clear()
        systemctl("daemon-reload")
    return tasindi
