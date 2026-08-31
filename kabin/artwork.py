from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


_TAG_PATTERN = re.compile(r"\s*[\[(][^\])]*[\])]\s*")
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def clean_game_title(filename: str) -> str:
    title = Path(filename).stem.replace("_", " ").strip()
    title = _TAG_PATTERN.sub(" ", title)
    return " ".join(title.split()).strip(" -") or Path(filename).stem


def artwork_root() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "kabin" / "console-art"


def cached_cover(game_id: str, root: Path | None = None) -> Path | None:
    digest = hashlib.sha256(game_id.encode()).hexdigest()
    directory = root or artwork_root()
    return next(
        (path for suffix in _IMAGE_SUFFIXES if (path := directory / f"{digest}{suffix}").is_file()),
        None,
    )


def local_cover(rom_path: Path) -> Path | None:
    candidates = []
    for suffix in _IMAGE_SUFFIXES:
        candidates.extend(
            (
                rom_path.with_suffix(suffix),
                rom_path.parent / "covers" / f"{rom_path.stem}{suffix}",
                rom_path.parent / "media" / f"{rom_path.stem}{suffix}",
            )
        )
    return next((path for path in candidates if path.is_file()), None)


def folder_cover(directory: Path) -> Path | None:
    if not directory.is_dir():
        return None
    for name in ("cover", "folder", "front", "album", "poster"):
        for suffix in _IMAGE_SUFFIXES:
            path = directory / f"{name}{suffix}"
            if path.is_file():
                return path
    return None


def _cache_key(game_id: str) -> str:
    return hashlib.sha256(game_id.encode()).hexdigest()


def _recent_miss(game_id: str, root: Path, max_age: int = 86400) -> bool:
    marker = root / f"{_cache_key(game_id)}.miss"
    try:
        return time.time() - marker.stat().st_mtime < max_age
    except OSError:
        return False


def _mark_miss(game_id: str, root: Path):
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{_cache_key(game_id)}.miss").touch()


def _json_request(url: str, api_key: str, opener=urllib.request.urlopen) -> dict:
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}", "User-Agent": "Kabin/0.1"},
    )
    with opener(request, timeout=15) as response:
        return json.loads(response.read())


def _supported_image(data: bytes) -> bool:
    return (
        data.startswith(b"\x89PNG\r\n\x1a\n")
        or data.startswith(b"\xff\xd8\xff")
        or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")
    )


def fetch_steamgriddb_cover(
    title: str,
    game_id: str,
    api_key: str,
    root: Path | None = None,
    opener=urllib.request.urlopen,
) -> Path | None:
    if not api_key:
        return None
    cache = root or artwork_root()
    existing = cached_cover(game_id, cache)
    if existing or _recent_miss(game_id, cache):
        return existing

    query = urllib.parse.quote(title, safe="")
    search = _json_request(
        f"https://www.steamgriddb.com/api/v2/search/autocomplete/{query}",
        api_key,
        opener,
    )
    results = search.get("data") or []
    if not results:
        _mark_miss(game_id, cache)
        return None
    match = next(
        (game for game in results if game.get("name", "").casefold() == title.casefold()),
        results[0],
    )
    grids = _json_request(
        "https://www.steamgriddb.com/api/v2/grids/game/"
        f"{match['id']}?dimensions=600x900&types=static",
        api_key,
        opener,
    ).get("data") or []
    portrait = next((grid for grid in grids if grid.get("height", 0) > grid.get("width", 0)), None)
    if not portrait:
        _mark_miss(game_id, cache)
        return None
    image_url = portrait.get("url", "")
    if urllib.parse.urlparse(image_url).scheme != "https":
        return None

    request = urllib.request.Request(image_url, headers={"User-Agent": "Kabin/0.1"})
    with opener(request, timeout=30) as response:
        data = response.read(15 * 1024 * 1024 + 1)
    if not data or len(data) > 15 * 1024 * 1024 or not _supported_image(data):
        return None
    destination = cache / f"{_cache_key(game_id)}.jpg"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".download")
    try:
        temporary.write_bytes(data)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    (cache / f"{_cache_key(game_id)}.miss").unlink(missing_ok=True)
    return destination


def resolve_local_cover(game_id: str, local_path: Path | None = None) -> Path | None:
    """Disk-only lookup so library refresh never waits on SteamGridDB."""
    return local_path or cached_cover(game_id)


def resolve_cover(
    title: str,
    game_id: str,
    artwork_config: dict | None,
    local_path: Path | None = None,
    fetch: bool = True,
):
    cover = resolve_local_cover(game_id, local_path)
    api_key = (artwork_config or {}).get("steamgriddb_api_key", "")
    if cover is None and fetch and api_key:
        try:
            cover = fetch_steamgriddb_cover(title, game_id, api_key)
        except (OSError, ValueError, KeyError):
            return None
    return cover


def fetch_remote_cover(
    host: dict,
    token: str,
    game_id: str,
    root: Path | None = None,
    opener=urllib.request.urlopen,
) -> Path | None:
    cache = root or (artwork_root().parent / "remote-art")
    cache_id = f"{host.get('name', '')}:{game_id}"
    existing = cached_cover(cache_id, cache)
    if existing:
        return existing
    query = urllib.parse.urlencode({"id": game_id})
    from .network import host_url, pinned_tls_context

    request = urllib.request.Request(
        host_url(host, f"/v1/artwork?{query}"),
        headers={"Authorization": f"Bearer {token}", "User-Agent": "Kabin/0.1"},
    )
    kwargs = {"timeout": 15}
    if opener is urllib.request.urlopen:
        kwargs["context"] = pinned_tls_context(host, 15)
    with opener(request, **kwargs) as response:
        data = response.read(15 * 1024 * 1024 + 1)
    if not data or len(data) > 15 * 1024 * 1024 or not _supported_image(data):
        return None
    if data.startswith(b"\x89PNG"):
        suffix = ".png"
    elif data.startswith(b"\xff\xd8\xff"):
        suffix = ".jpg"
    else:
        suffix = ".webp"
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / f"{_cache_key(cache_id)}{suffix}"
    temporary = destination.with_suffix(".download")
    try:
        temporary.write_bytes(data)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
