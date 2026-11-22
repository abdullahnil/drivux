"""Kullanım:
  drive-baglanti            Arayüzü açar
  drive-baglanti servis     Eşitleme servisini çalıştırır (systemd kullanır)
  drive-baglanti disk       Google Drive'ı disk olarak bağlar (systemd kullanır)
  drive-baglanti ayir       Diski ayırır
  drive-baglanti esitle     Servisten hemen eşitlemesini ister
  drive-baglanti durum      Eşitleme durumunu yazdırır
"""

import sys


def main() -> int:
    komut = sys.argv[1] if len(sys.argv) > 1 else ""
    if komut == "servis":
        from .servis import main as servis
        servis()
    elif komut == "disk":
        from .servis import disk_bagla
        disk_bagla()
    elif komut == "ayir":
        from .servis import disk_ayir
        disk_ayir()
    elif komut == "esitle":
        from . import ortak
        ortak.servise_sinyal("USR1")
        print("Eşitleme istendi.")
    elif komut == "durum":
        import json
        from . import ortak
        print(json.dumps(ortak.durum_oku(), ensure_ascii=False, indent=2))
    elif komut in ("", "arayuz"):
        from .arayuz import main as arayuz
        return arayuz()
    else:
        print(__doc__)
        return 0 if komut in ("-h", "--help", "yardim") else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
