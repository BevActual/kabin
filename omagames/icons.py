import os
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from gi.repository import GLib

_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "omagames" / "steam"

_URL_TEMPLATES = [
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_600x900.jpg",
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg",
]

_inflight = set()


def cached_path(appid: str) -> Optional[Path]:
    p = _CACHE_DIR / f"{appid}.jpg"
    return p if p.exists() else None


def fetch_async(appid: str, on_done: Callable[[Optional[Path]], None]) -> None:
    """Downloads Steam grid artwork in a background thread.

    `on_done(path_or_None)` is invoked on the GLib main loop thread.
    """
    if appid in _inflight:
        return
    _inflight.add(appid)

    def worker():
        dest = _CACHE_DIR / f"{appid}.jpg"
        result = None
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            for template in _URL_TEMPLATES:
                url = template.format(appid=appid)
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": "omagames/0.1"})
                    with urllib.request.urlopen(request, timeout=6) as resp:
                        data = resp.read()
                    tmp = dest.with_suffix(".tmp")
                    tmp.write_bytes(data)
                    tmp.rename(dest)
                    result = dest
                    break
                except (urllib.error.URLError, OSError, TimeoutError):
                    continue
        finally:
            _inflight.discard(appid)
            GLib.idle_add(on_done, result)

    threading.Thread(target=worker, daemon=True).start()
