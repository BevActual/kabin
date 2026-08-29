import os
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from gi.repository import GLib

_CACHE_ROOT = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "kabin" / "steam"
_LEGACY_CACHE_ROOT = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "omagames" / "steam"
)

_ASSET_SPECS = {
    "cover": {
        "ext": "jpg",
        "urls": [
            "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_600x900.jpg",
            "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg",
        ],
    },
    "logo": {
        "ext": "png",
        "urls": [
            "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/logo.png",
        ],
    },
}

_inflight = set()


def cached_path(appid: str, kind: str = "cover") -> Optional[Path]:
    spec = _ASSET_SPECS[kind]
    p = _CACHE_ROOT / kind / f"{appid}.{spec['ext']}"
    if p.exists():
        return p
    legacy = _LEGACY_CACHE_ROOT / kind / f"{appid}.{spec['ext']}"
    return legacy if legacy.exists() else None


def fetch_async(appid: str, on_done: Callable[[Optional[Path]], None], kind: str = "cover") -> None:
    """Downloads Steam grid/logo artwork in a background thread.

    `on_done(path_or_None)` is invoked on the GLib main loop thread. `kind`
    is "cover" (portrait library art) or "logo" (transparent clear-logo).
    """
    key = (kind, appid)
    if key in _inflight:
        return
    _inflight.add(key)

    spec = _ASSET_SPECS[kind]
    cache_dir = _CACHE_ROOT / kind

    def worker():
        dest = cache_dir / f"{appid}.{spec['ext']}"
        result = None
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            for template in spec["urls"]:
                url = template.format(appid=appid)
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": "kabin/0.1"})
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
            _inflight.discard(key)
            GLib.idle_add(on_done, result)

    threading.Thread(target=worker, daemon=True).start()
