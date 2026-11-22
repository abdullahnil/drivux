"""Usage:
  drivux               Open the app
  drivux sync          Ask the service to sync now          (esitle)
  drivux status        Print the sync status as JSON        (durum)
  drivux tray          Show the top bar icon                (tepsi)
  drivux update        Check for updates and offer to install one   (guncelle)
  drivux service       Run the sync service (used by systemd)   (servis)
  drivux mount         Mount Google Drive (used by systemd)     (disk)
  drivux unmount       Unmount Google Drive                     (ayir)
"""

import sys


def main() -> int:
    komut = sys.argv[1] if len(sys.argv) > 1 else ""
    if komut in ("service", "servis"):
        from .servis import main as servis
        servis()
    elif komut in ("mount", "disk"):
        from .servis import disk_bagla
        disk_bagla()
    elif komut in ("warm", "isit"):
        from .servis import disk_isit
        disk_isit()
    elif komut in ("unmount", "ayir"):
        from .servis import disk_ayir
        disk_ayir()
    elif komut in ("sync", "esitle"):
        from . import ortak
        from .ceviri import _
        ortak.servise_sinyal("USR1")
        print(_("Sync requested."))
    elif komut in ("status", "durum"):
        import json
        from . import ortak
        print(json.dumps(ortak.durum_oku(), ensure_ascii=False, indent=2))
    elif komut in ("tray", "tepsi"):
        from .tepsi import main as tepsi
        return tepsi()
    elif komut in ("update", "guncelle"):
        from .arayuz import guncelleme_ac
        return guncelleme_ac()
    elif komut in ("", "app", "arayuz"):
        from .arayuz import main as arayuz
        return arayuz()
    else:
        print(__doc__)
        return 0 if komut in ("-h", "--help", "help", "yardim") else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
