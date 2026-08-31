from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ..artwork import book_artwork_root, cached_cover, extract_epub_cover, folder_cover, local_cover
from ..kinds import FOLDER_KINDS, get_kind
from ..models import LibraryItem
from ..titles import parse_media_name

_SKIP_DIRS = {"covers", "media", "images", "manuals", "videos", ".git"}


def _iter_files(base: Path):
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name.casefold() not in _SKIP_DIRS and not name.startswith(".")
        )
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            path = Path(dirpath) / name
            if path.is_file() and not path.is_symlink():
                yield path


def _item_id(kind_id: str, base: Path, target: Path) -> str:
    try:
        relative = target.relative_to(base)
    except ValueError:
        return f"{kind_id}:{target.name}"
    if relative.parent == Path("."):
        return f"{kind_id}:{target.name}"
    return f"{kind_id}:{relative.as_posix()}"


def _open(path: Path):
    subprocess.Popen(["xdg-open", str(path)], start_new_session=True)


def _cover_for(path: Path) -> Path | None:
    return local_cover(path) or folder_cover(path.parent) or extract_epub_cover(path)


def _file_item(kind, base: Path, path: Path, hidden_ids) -> LibraryItem | None:
    item_id = _item_id(kind.id, base, path)
    if item_id in hidden_ids:
        return None
    parsed = parse_media_name(path.name, kind.id)
    cover = _cover_for(path)
    if cover is None and kind.id == "book":
        cover = cached_cover(item_id, book_artwork_root())
    return LibraryItem(
        id=item_id,
        title=parsed.title,
        source=kind.source,
        subtitle=kind.label,
        icon_path=str(cover) if cover else None,
        icon_name=kind.icon,
        launch=lambda target=path: _open(target),
        extra={
            "path": str(path),
            "added_at": path.stat().st_mtime,
            "needs_artwork": cover is None and kind.id == "book",
        },
        media_type=kind.id,
        media_format=path.suffix.lower().lstrip("."),
        creators=list(parsed.creators),
        series=parsed.series,
        series_index=parsed.series_index,
    )


def _album_item(kind, base: Path, folder: Path, tracks: list[Path], hidden_ids) -> LibraryItem | None:
    item_id = _item_id(kind.id, base, folder)
    if item_id in hidden_ids:
        return None
    parsed = parse_media_name(folder.name, kind.id)
    cover = folder_cover(folder) or local_cover(tracks[0])
    return LibraryItem(
        id=item_id,
        title=parsed.title,
        source=kind.source,
        subtitle=kind.plural,
        icon_path=str(cover) if cover else None,
        icon_name=kind.icon,
        launch=lambda target=folder: _open(target),
        extra={
            "path": str(folder),
            "added_at": folder.stat().st_mtime,
            "track_count": len(tracks),
        },
        media_type=kind.id,
        media_format="album",
        creators=list(parsed.creators),
        series=parsed.series,
        series_index=parsed.series_index,
    )


def _scan_kind(kind, base: Path, hidden_ids) -> list[LibraryItem]:
    if kind.id == "music":
        albums: dict[Path, list[Path]] = {}
        loose: list[Path] = []
        for path in _iter_files(base):
            if path.suffix.lower() not in kind.extensions:
                continue
            if path.parent == base:
                loose.append(path)
            else:
                albums.setdefault(path.parent, []).append(path)
        items = []
        for folder, tracks in sorted(albums.items()):
            item = _album_item(kind, base, folder, tracks, hidden_ids)
            if item:
                items.append(item)
        for path in loose:
            item = _file_item(kind, base, path, hidden_ids)
            if item:
                items.append(item)
        return items

    items = []
    for path in _iter_files(base):
        if path.suffix.lower() not in kind.extensions:
            continue
        item = _file_item(kind, base, path, hidden_ids)
        if item:
            items.append(item)
    return items


def get_items(media_dirs, hidden_ids=None, enabled_kinds=None) -> list[LibraryItem]:
    hidden_ids = hidden_ids or set()
    items = []
    allowed = {kind.id for kind in FOLDER_KINDS}
    if enabled_kinds is not None:
        allowed &= set(enabled_kinds)
    for entry in media_dirs:
        kind = get_kind(entry.get("media_type"))
        if kind.id not in allowed:
            continue
        base = Path(entry.get("path", "")).expanduser()
        if not base.is_dir():
            continue
        items.extend(_scan_kind(kind, base, hidden_ids))
    return items
