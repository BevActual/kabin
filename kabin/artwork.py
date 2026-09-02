from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .titles import restore_leading_article


_TAG_PATTERN = re.compile(r"\s*[\[(][^\])]*[\])]\s*")
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def clean_game_title(filename: str) -> str:
    title = Path(filename).stem.replace("_", " ").strip()
    title = _TAG_PATTERN.sub(" ", title)
    title = " ".join(title.split()).strip(" -") or Path(filename).stem
    return restore_leading_article(title)


def artwork_root() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "kabin" / "console-art"


def book_artwork_root() -> Path:
    return artwork_root().parent / "book-art"


def chosen_artwork_root() -> Path:
    return artwork_root().parent / "chosen-art"


@dataclass(frozen=True)
class CoverCandidate:
    image_url: str
    caption: str
    thumb_url: str = ""
    source: str = ""


def cached_cover(game_id: str, root: Path | None = None) -> Path | None:
    digest = hashlib.sha256(game_id.encode()).hexdigest()
    directory = root or artwork_root()
    # Skip the four suffix probes when the cache dir was never created.
    if not directory.is_dir():
        return None
    for suffix in _IMAGE_SUFFIXES:
        path = directory / f"{digest}{suffix}"
        if path.is_file():
            return path
    return None


def local_cover(rom_path: Path) -> Path | None:
    """Sidecar art beside the ROM, then in covers/ or media/.

    Checks layouts in order and returns on the first hit so a library with
    covers next to the ROMs pays one `is_file` per title, and a library
    without a covers/ folder skips those four probes entirely."""
    parent = rom_path.parent
    for suffix in _IMAGE_SUFFIXES:
        path = rom_path.with_suffix(suffix)
        if path.is_file():
            return path
    stem = rom_path.stem
    for subdir in ("covers", "media"):
        folder = parent / subdir
        if not folder.is_dir():
            continue
        for suffix in _IMAGE_SUFFIXES:
            path = folder / f"{stem}{suffix}"
            if path.is_file():
                return path
    return None


def folder_cover(directory: Path) -> Path | None:
    if not directory.is_dir():
        return None
    for name in ("cover", "folder", "front", "album", "poster"):
        for suffix in _IMAGE_SUFFIXES:
            path = directory / f"{name}{suffix}"
            if path.is_file():
                return path
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _epub_cover_href(opf_root) -> str | None:
    cover_id = ""
    for meta in opf_root.iter():
        if _local_name(meta.tag) != "meta":
            continue
        name = (meta.get("name") or meta.get("property") or "").lower()
        if name in {"cover", "cover-image"}:
            cover_id = (meta.get("content") or (meta.text or "")).strip()
            if cover_id:
                break
    items = [item for item in opf_root.iter() if _local_name(item.tag) == "item"]
    for item in items:
        props = (item.get("properties") or "").split()
        if "cover-image" in props or (cover_id and item.get("id") == cover_id):
            return item.get("href")
    for item in items:
        href = item.get("href") or ""
        media = (item.get("media-type") or "").lower()
        if "cover" in (item.get("id") or "").lower() or "cover" in href.lower():
            if media.startswith("image/") or href.lower().endswith(_IMAGE_SUFFIXES):
                return href
    for item in items:
        href = item.get("href") or ""
        media = (item.get("media-type") or "").lower()
        if media.startswith("image/") or href.lower().endswith(_IMAGE_SUFFIXES):
            return href
    return None


def _image_suffix(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    return ".webp"


def extract_epub_cover(path: Path, root: Path | None = None) -> Path | None:
    if path.suffix.lower() != ".epub" or not path.is_file():
        return None
    cache_id = f"epub:{path.resolve()}"
    cache = root or (artwork_root().parent / "media-covers")
    existing = cached_cover(cache_id, cache)
    if existing:
        return existing
    if _recent_miss(cache_id, cache):
        return None
    try:
        with zipfile.ZipFile(path) as archive:
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            rootfile = next(
                (
                    node
                    for node in container.iter()
                    if _local_name(node.tag) == "rootfile" and node.get("full-path")
                ),
                None,
            )
            if rootfile is None:
                raise KeyError("rootfile")
            opf_path = rootfile.get("full-path")
            opf = ET.fromstring(archive.read(opf_path))
            href = _epub_cover_href(opf)
            if not href:
                raise KeyError("cover")
            cover_path = posixpath.normpath(
                posixpath.join(posixpath.dirname(opf_path), urllib.parse.unquote(href))
            )
            data = archive.read(cover_path)
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, ET.ParseError):
        _mark_miss(cache_id, cache)
        return None
    if not data or len(data) > 15 * 1024 * 1024 or not _supported_image(data):
        _mark_miss(cache_id, cache)
        return None
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / f"{_cache_key(cache_id)}{_image_suffix(data)}"
    temporary = destination.with_suffix(".download")
    try:
        temporary.write_bytes(data)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


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


def _public_json(url: str, opener=urllib.request.urlopen) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Kabin/0.1"})
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


def _best_openlibrary_doc(docs: list, title: str, author: str):
    title_cf = title.casefold().strip()
    author_cf = author.casefold().strip()
    scored = []
    for doc in docs:
        if not doc.get("cover_i"):
            continue
        doc_title = (doc.get("title") or "").casefold()
        authors = [name.casefold() for name in (doc.get("author_name") or [])]
        score = 0
        if doc_title == title_cf:
            score += 3
        elif title_cf and (title_cf in doc_title or doc_title in title_cf):
            score += 1
        if author_cf and any(author_cf in name or name in author_cf for name in authors):
            score += 2
        if score:
            scored.append((score, doc))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def fetch_openlibrary_cover(
    title: str,
    author: str,
    item_id: str,
    root: Path | None = None,
    opener=urllib.request.urlopen,
) -> Path | None:
    title = (title or "").strip()
    if not title:
        return None
    cache = root or book_artwork_root()
    existing = cached_cover(item_id, cache)
    if existing or _recent_miss(item_id, cache):
        return existing

    query = {"title": title, "limit": "8", "fields": "key,title,author_name,cover_i"}
    if author:
        query["author"] = author
    search = _public_json(
        "https://openlibrary.org/search.json?" + urllib.parse.urlencode(query),
        opener,
    )
    match = _best_openlibrary_doc(search.get("docs") or [], title, author)
    if not match:
        _mark_miss(item_id, cache)
        return None
    image_url = f"https://covers.openlibrary.org/b/id/{int(match['cover_i'])}-L.jpg"
    request = urllib.request.Request(image_url, headers={"User-Agent": "Kabin/0.1"})
    with opener(request, timeout=30) as response:
        data = response.read(15 * 1024 * 1024 + 1)
    if not data or len(data) < 2048 or len(data) > 15 * 1024 * 1024 or not _supported_image(data):
        _mark_miss(item_id, cache)
        return None
    destination = cache / f"{_cache_key(item_id)}{_image_suffix(data)}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".download")
    try:
        temporary.write_bytes(data)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    (cache / f"{_cache_key(item_id)}.miss").unlink(missing_ok=True)
    return destination


def _https_image(url: str, opener=urllib.request.urlopen, timeout: int = 30) -> bytes | None:
    if urllib.parse.urlparse(url).scheme != "https":
        return None
    request = urllib.request.Request(url, headers={"User-Agent": "Kabin/0.1"})
    with opener(request, timeout=timeout) as response:
        data = response.read(15 * 1024 * 1024 + 1)
    if not data or len(data) > 15 * 1024 * 1024 or not _supported_image(data):
        return None
    return data


def save_chosen_cover(item_id: str, data: bytes, root: Path | None = None) -> Path | None:
    if not item_id or not data or len(data) > 15 * 1024 * 1024 or not _supported_image(data):
        return None
    cache = root or chosen_artwork_root()
    cache.mkdir(parents=True, exist_ok=True)
    digest = _cache_key(item_id)
    for path in cache.glob(f"{digest}.*"):
        if path.suffix != ".download":
            path.unlink(missing_ok=True)
    destination = cache / f"{digest}{_image_suffix(data)}"
    temporary = destination.with_suffix(".download")
    try:
        temporary.write_bytes(data)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def install_cover_from_url(
    item_id: str,
    url: str,
    root: Path | None = None,
    opener=urllib.request.urlopen,
) -> Path | None:
    data = _https_image(url, opener)
    if not data:
        return None
    return save_chosen_cover(item_id, data, root)


def install_cover_from_file(item_id: str, path: Path, root: Path | None = None) -> Path | None:
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    return save_chosen_cover(item_id, data, root)


def apply_chosen_covers(items, covers: dict) -> None:
    for item in items:
        path = Path(covers.get(item.id, "")).expanduser() if covers.get(item.id) else None
        if path and path.is_file():
            item.icon_path = str(path)
            item.extra["needs_artwork"] = False


def search_steamgriddb_candidates(
    title: str,
    api_key: str,
    opener=urllib.request.urlopen,
    limit: int = 12,
) -> list[CoverCandidate]:
    title = (title or "").strip()
    if not title or not api_key:
        return []
    query = urllib.parse.quote(title, safe="")
    search = _json_request(
        f"https://www.steamgriddb.com/api/v2/search/autocomplete/{query}",
        api_key,
        opener,
    )
    games = (search.get("data") or [])[:3]
    candidates = []
    seen = set()
    for game in games:
        game_id = game.get("id")
        name = game.get("name") or title
        if not game_id:
            continue
        grids = (
            _json_request(
                "https://www.steamgriddb.com/api/v2/grids/game/"
                f"{game_id}?types=static",
                api_key,
                opener,
            ).get("data")
            or []
        )
        for grid in grids:
            url = grid.get("url") or ""
            if not url or url in seen or urllib.parse.urlparse(url).scheme != "https":
                continue
            seen.add(url)
            style = grid.get("style") or ""
            caption = f"{name} · {style}" if style else name
            candidates.append(
                CoverCandidate(
                    image_url=url,
                    thumb_url=grid.get("thumb") or url,
                    caption=caption,
                    source="steamgriddb",
                )
            )
            if len(candidates) >= limit:
                return candidates
    return candidates


def search_openlibrary_candidates(
    title: str,
    author: str = "",
    opener=urllib.request.urlopen,
    limit: int = 12,
) -> list[CoverCandidate]:
    title = (title or "").strip()
    if not title:
        return []
    query = {"title": title, "limit": "16", "fields": "key,title,author_name,cover_i"}
    if author:
        query["author"] = author
    search = _public_json(
        "https://openlibrary.org/search.json?" + urllib.parse.urlencode(query),
        opener,
    )
    candidates = []
    seen = set()
    for doc in search.get("docs") or []:
        cover_id = doc.get("cover_i")
        if not cover_id or cover_id in seen:
            continue
        seen.add(cover_id)
        name = doc.get("title") or title
        creators = ", ".join((doc.get("author_name") or [])[:2])
        caption = f"{name} · {creators}" if creators else name
        image_url = f"https://covers.openlibrary.org/b/id/{int(cover_id)}-L.jpg"
        thumb_url = f"https://covers.openlibrary.org/b/id/{int(cover_id)}-M.jpg"
        candidates.append(
            CoverCandidate(
                image_url=image_url,
                thumb_url=thumb_url,
                caption=caption,
                source="openlibrary",
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def search_coverartarchive_candidates(
    title: str,
    artist: str = "",
    opener=urllib.request.urlopen,
    limit: int = 8,
) -> list[CoverCandidate]:
    title = (title or "").strip()
    if not title:
        return []
    query = f'release:"{title}"'
    artist = (artist or "").strip()
    if artist:
        query += f' AND artist:"{artist}"'
    search = _public_json(
        "https://musicbrainz.org/ws/2/release/?"
        + urllib.parse.urlencode({"query": query, "fmt": "json", "limit": "8"}),
        opener,
    )
    candidates = []
    for release in search.get("releases") or []:
        mbid = release.get("id")
        if not mbid:
            continue
        name = release.get("title") or title
        credits = [
            part.get("name")
            for part in (release.get("artist-credit") or [])
            if isinstance(part, dict) and part.get("name")
        ]
        caption = f"{name} · {', '.join(credits)}" if credits else name
        image_url = f"https://coverartarchive.org/release/{mbid}/front-500"
        candidates.append(
            CoverCandidate(
                image_url=image_url,
                thumb_url=f"https://coverartarchive.org/release/{mbid}/front-250",
                caption=caption,
                source="coverartarchive",
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def search_cover_candidates(
    title: str,
    media_type: str,
    *,
    creator: str = "",
    api_key: str = "",
    opener=urllib.request.urlopen,
) -> list[CoverCandidate]:
    kind = media_type or "game"
    if kind in {"book", "comic"}:
        return search_openlibrary_candidates(title, creator, opener)
    if kind == "music":
        return search_coverartarchive_candidates(title, creator, opener)
    return search_steamgriddb_candidates(title, api_key, opener)


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
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / f"{_cache_key(cache_id)}{_image_suffix(data)}"
    temporary = destination.with_suffix(".download")
    try:
        temporary.write_bytes(data)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
