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

_lock = threading.Lock()
_inflight: dict[tuple, list[Callable]] = {}


def _supported_image(data: bytes) -> bool:
    return (
        data.startswith(b"\x89PNG\r\n\x1a\n")
        or data.startswith(b"\xff\xd8\xff")
        or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")
    )


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
    Duplicate in-flight requests share one download and every listener is notified.
    """
    key = (kind, appid)
    with _lock:
        listeners = _inflight.get(key)
        if listeners is not None:
            listeners.append(on_done)
            return
        _inflight[key] = [on_done]

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
                        data = resp.read(15 * 1024 * 1024 + 1)
                    if not data or len(data) > 15 * 1024 * 1024 or not _supported_image(data):
                        continue
                    tmp = dest.with_suffix(".tmp")
                    tmp.write_bytes(data)
                    tmp.replace(dest)
                    result = dest
                    break
                except (urllib.error.URLError, OSError, TimeoutError):
                    continue
        finally:
            with _lock:
                callbacks = _inflight.pop(key, [])
            for callback in callbacks:
                GLib.idle_add(callback, result)

    threading.Thread(target=worker, daemon=True).start()
