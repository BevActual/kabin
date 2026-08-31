from __future__ import annotations

import time

from .kinds import KINDS, kind_for


SHELF_LIMIT = 8
LONELY_TILE_SCALE = 1.28
ADDED_MIN_LIBRARY = 5
LIBRARY_SORT_MIN = 6
PORTRAIT_BLEED_SHAPES = frozenset({"landscape"})


def continue_heading(kind) -> str:
    return f"Continue · {kind.plural}"


def added_heading(kind) -> str:
    return f"Recently added · {kind.plural}"


def _kind_order(games, recent_ids: list[str]) -> list[str]:
    by_id = {item.id: item for item in games}
    order = []
    seen = set()
    for item_id in recent_ids:
        item = by_id.get(item_id)
        if item is None:
            continue
        kind_id = kind_for(item).id
        if kind_id not in seen:
            seen.add(kind_id)
            order.append(kind_id)
    for kind_id in KINDS:
        if kind_id not in seen:
            order.append(kind_id)
    return order


def split_home_shelves(games, recent_ids: list[str], featured_id: str | None = None, limit: int = SHELF_LIMIT):
    """Split Continue and Recently Added into per-library rows.

    Featured and in-progress titles stay out of the added rows so Home
    does not repeat the same jacket three times.
    """
    by_id = {item.id: item for item in games}
    continue_rows = []
    continue_ids = set()
    for kind_id in _kind_order(games, recent_ids):
        items = []
        for item_id in recent_ids:
            item = by_id.get(item_id)
            if item is None or kind_for(item).id != kind_id:
                continue
            if featured_id and item.id == featured_id:
                continue
            items.append(item)
            if len(items) >= limit:
                break
        if items:
            continue_rows.append((KINDS[kind_id], items))
            continue_ids.update(item.id for item in items)

    added_rows = []
    for kind_id in KINDS:
        added = [
            item
            for item in games
            if kind_for(item).id == kind_id and item.extra.get("added_at")
        ]
        added.sort(key=lambda item: item.extra.get("added_at") or 0, reverse=True)
        added = [
            item
            for item in added
            if item.id not in continue_ids and item.id != featured_id
        ][:limit]
        kind_total = sum(1 for item in games if kind_for(item).id == kind_id)
        if added and kind_total >= ADDED_MIN_LIBRARY:
            added_rows.append((KINDS[kind_id], added))
    return continue_rows, added_rows


def hero_meta_line(item) -> str:
    parts = []
    creators = [name for name in (getattr(item, "creators", None) or []) if name]
    if creators:
        parts.append(creators[0])
    series = getattr(item, "series", "") or ""
    if series and series not in parts:
        parts.append(series)
    return " · ".join(parts)


def continue_tile_scale(count: int) -> float:
    return LONELY_TILE_SCALE if count == 1 else 1.0


def library_tile_scale(count: int) -> float:
    """Grow lockups when a typed library would otherwise sit in a hole."""
    if count <= 1:
        return 1.7
    if count <= 3:
        return 1.5
    if count <= 6:
        return 1.18
    return 1.0


def show_library_sort(count: int) -> bool:
    return count >= LIBRARY_SORT_MIN


def hero_uses_bleed(kind) -> bool:
    return getattr(kind, "shape", "") in PORTRAIT_BLEED_SHAPES


def opened_caption(timestamp: float, now: float | None = None) -> str:
    if not timestamp:
        return ""
    now = time.time() if now is None else now
    delta = max(0.0, now - float(timestamp))
    if delta < 90:
        return "Opened just now"
    if delta < 3600:
        minutes = int(delta // 60)
        return "Opened a minute ago" if minutes == 1 else f"Opened {minutes} minutes ago"
    if delta < 86400:
        hours = int(delta // 3600)
        return "Opened an hour ago" if hours == 1 else f"Opened {hours} hours ago"
    days = int(delta // 86400)
    if days == 1:
        return "Opened yesterday"
    if days < 7:
        return f"Opened {days} days ago"
    return time.strftime("Opened %b %d", time.localtime(timestamp)).replace(" 0", " ")


def continue_caption(
    *,
    playing: bool = False,
    track: int = 0,
    tracks: int = 1,
    clock: str = "",
    opened_at: float = 0,
    now: float | None = None,
    fallback: str = "",
) -> str:
    if playing:
        return "Now playing"
    if tracks > 1 and (track or clock):
        parts = [f"Track {track + 1}"]
        if clock:
            parts.append(clock)
        return "Resume · " + " · ".join(parts)
    if clock:
        return f"Resume · {clock}"
    return opened_caption(opened_at, now) or fallback


def move_home_focus(row_lengths: list[int], row: int, col: int, action: str):
    """Move couch focus on Home. None means leave the page for the sidebar."""
    if not row_lengths:
        return None
    row = max(0, min(row, len(row_lengths) - 1))
    width = max(1, row_lengths[row])
    col = max(0, min(col, width - 1))
    if action == "left":
        return (row, col - 1) if col > 0 else None
    if action == "right":
        return (row, min(width - 1, col + 1))
    if action == "up":
        if row == 0:
            return row, col
        row -= 1
        return row, min(col, max(0, row_lengths[row] - 1))
    if action == "down":
        if row + 1 >= len(row_lengths):
            return row, col
        row += 1
        return row, min(col, max(0, row_lengths[row] - 1))
    return row, col
