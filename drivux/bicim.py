"""Text formatting shared by the app and the tray icon (no GTK here)."""

import time

from .ceviri import _, _n


def gecen_sure(ts: float | None) -> str:
    if not ts:
        return _("not yet")
    s = int(time.time() - ts)
    if s < 60:
        return _("just now")
    if s < 3600:
        return _("{n} min ago").format(n=s // 60)
    if s < 86400:
        return _n("{n} hour ago", "{n} hours ago", s // 3600).format(n=s // 3600)
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def boyut(b: float) -> str:
    for birim in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024 or birim == "TB":
            return f"{b:.1f} {birim}" if birim != "B" else f"{int(b)} B"
        b /= 1024
