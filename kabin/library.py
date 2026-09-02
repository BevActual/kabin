"""Pure library filtering, sorting, and playability logic.

Extracted out of MainWindow so it can be tested without a live GTK window.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .kinds import FOLDER_KINDS, kind_for
from .network import media_stream_url
from .systems import SYSTEMS
from .playback import (
    format_clock,
    local_queue,
    page_progress_ratio,
    playable_file,
    plays_in_kabin,
    progress_ratio,
    resume_seconds,
    resume_track,
    should_resume,
    track_count,
)
from .reader import READABLE_KINDS, opens_in_kabin_reader, reader_backend_for, resume_page

CATEGORY_HOME = ("home", None)
CATEGORY_FAVORITES = ("favorite", None)
CATEGORY_GAMES = ("type", "game")
CATEGORY_READING = ("reading", None)
CATEGORY_WATCHING = ("watching", None)
READING_KINDS = ("book", "comic")
WATCHING_KINDS = ("video", "tv")


@dataclass(frozen=True)
class LibraryGroup:
    category: tuple
    label: str
    icon_key: str
    kind_ids: tuple[str, ...]
    chips: tuple[tuple[str, str], ...]
    tile_kind: str


READING_GROUP = LibraryGroup(
    CATEGORY_READING, "Books", "book", READING_KINDS, (("book", "Books"), ("comic", "Comics")), "book"
)
WATCHING_GROUP = LibraryGroup(
    CATEGORY_WATCHING, "Movies", "video", WATCHING_KINDS, (("video", "Movies"), ("tv", "TV")), "video"
)
LIBRARY_GROUPS = (READING_GROUP, WATCHING_GROUP)
_GROUP_BY_KIND = {kind_id: group for group in LIBRARY_GROUPS for kind_id in group.kind_ids}
_GROUP_BY_KEY = {group.category[0]: group for group in LIBRARY_GROUPS}
_GROUPED_KIND_IDS = frozenset(_GROUP_BY_KIND)


@dataclass(frozen=True)
class SidebarEntry:
    kind: str
    label: str
    icon_key: str = ""
    count: int | str | None = None
    category: tuple | None = None


def library_group_for(category) -> LibraryGroup | None:
    kind, value = category
    if kind in _GROUP_BY_KEY:
        return _GROUP_BY_KEY[kind]
    if kind == "type":
        return _GROUP_BY_KIND.get(value)
    return None


def sidebar_highlight_category(category):
    """Nested filters stay on their parent library row."""
    kind, _value = category
    if kind in {"system", "source"}:
        return CATEGORY_GAMES
    group = library_group_for(category)
    if group:
        return group.category
    return category


def sidebar_entries(games, config, host_statuses=None) -> list[SidebarEntry]:
    """Library destinations first; systems and Settings stay off this list."""
    host_statuses = host_statuses or {}
    entries = [
        SidebarEntry("row", "Home", "home", None, CATEGORY_HOME),
    ]
    favorite_count = sum(1 for game in games if config.is_favorite(game.id))
    if favorite_count:
        entries.append(
            SidebarEntry("row", "Favorites", "favorites", favorite_count, CATEGORY_FAVORITES)
        )
    game_count = sum(1 for item in games if kind_for(item).id == "game")
    entries.append(SidebarEntry("row", "Games", "all", game_count, CATEGORY_GAMES))
    for group in LIBRARY_GROUPS:
        count = sum(1 for item in games if kind_for(item).id in group.kind_ids)
        if count:
            entries.append(
                SidebarEntry("row", group.label, group.icon_key, count, group.category)
            )
    for kind in FOLDER_KINDS:
        if kind.id in _GROUPED_KIND_IDS:
            continue
        count = sum(1 for item in games if kind_for(item).id == kind.id)
        if count:
            entries.append(SidebarEntry("row", kind.plural, kind.id, count, ("type", kind.id)))

    remote_hosts = {game.subtitle for game in games if game.source == "remote" and game.subtitle}
    remote_hosts.update(
        host.get("name")
        for host in config.network.get("remote_hosts", [])
        if host.get("name")
    )
    if remote_hosts:
        entries.append(SidebarEntry("header", "HOSTS"))
        for host in sorted(remote_hosts):
            count = sum(1 for game in games if game.source == "remote" and game.subtitle == host)
            status = host_statuses.get(host, {})
            state = status.get("state")
            if state == "auth":
                badge = "Re-pair"
            elif state == "offline":
                badge = "Offline"
            elif state == "checking":
                badge = "…"
            else:
                badge = count
            icon = "network-offline" if state in {"auth", "offline"} else "remote"
            entries.append(SidebarEntry("row", host, icon, badge, ("host", host)))
    return entries


def game_library_filters(games) -> list[tuple[tuple, str, int]]:
    """All / Steam / consoles chips shown on the Games page."""
    filters = [
        (CATEGORY_GAMES, "All", sum(1 for game in games if kind_for(game).id == "game")),
    ]
    steam = sum(1 for game in games if game.source == "steam")
    if steam:
        filters.append((("source", "steam"), "Steam", steam))
    desktop = sum(1 for game in games if game.source == "desktop")
    if desktop:
        filters.append((("source", "desktop"), "Other Apps", desktop))
    by_system = {}
    for game in games:
        if game.source == "roms" and game.subtitle:
            by_system[game.subtitle] = by_system.get(game.subtitle, 0) + 1
    known = {system.name for system in SYSTEMS}
    for system in SYSTEMS:
        count = by_system.get(system.name, 0)
        if count:
            filters.append((("system", system.name), system.chip_label, count))
    for name in sorted(name for name in by_system if name not in known):
        filters.append((("system", name), name, by_system[name]))
    return filters


def grouped_library_filters(group: LibraryGroup, games) -> list[tuple[tuple, str, int]]:
    counts = {
        kind_id: sum(1 for game in games if kind_for(game).id == kind_id)
        for kind_id in group.kind_ids
    }
    total = sum(counts.values())
    filters = [(group.category, "All", total)]
    if sum(1 for count in counts.values() if count) < 2:
        return filters
    for kind_id, label in group.chips:
        if counts[kind_id]:
            filters.append((("type", kind_id), label, counts[kind_id]))
    return filters


def reading_library_filters(games) -> list[tuple[tuple, str, int]]:
    return grouped_library_filters(READING_GROUP, games)


def watching_library_filters(games) -> list[tuple[tuple, str, int]]:
    return grouped_library_filters(WATCHING_GROUP, games)


def library_scope_filters(category, games) -> list[tuple[tuple, str, int]]:
    highlight = sidebar_highlight_category(category)
    if highlight == CATEGORY_GAMES:
        return game_library_filters(games)
    group = library_group_for(highlight)
    if group:
        return grouped_library_filters(group, games)
    return []


def matches_context(game, search_text: str, category, config) -> bool:
    if search_text and search_text not in game.search_text:
        return False
    kind, value = category
    if kind in ("home", "all"):
        return True
    group = _GROUP_BY_KEY.get(kind)
    if group:
        return kind_for(game).id in group.kind_ids
    if kind == "type":
        return kind_for(game).id == value
    if kind == "preset" and value == "unplayed":
        return game.id not in config.recent
    if kind == "favorite":
        return config.is_favorite(game.id)
    if kind == "source":
        return game.source == value
    if kind == "system":
        return game.source == "roms" and game.subtitle == value
    if kind == "host":
        return game.source == "remote" and game.subtitle == value
    return True


def matches(
    game,
    search_text: str,
    category,
    config,
    *,
    favorites_only: bool = False,
    unplayed_only: bool = False,
    location_filter: str = "all",
) -> bool:
    if not matches_context(game, search_text, category, config):
        return False
    if favorites_only and not config.is_favorite(game.id):
        return False
    if unplayed_only and game.id in config.recent:
        return False
    if location_filter == "local" and game.source == "remote":
        return False
    if location_filter == "remote" and game.source != "remote":
        return False
    return True


def compare_items(game_a, game_b, sort_mode: str, config) -> int:
    if sort_mode == "recent":
        recent = config.recent
        time_a = recent.get(game_a.id, 0)
        time_b = recent.get(game_b.id, 0)
        if time_a != time_b:
            return -1 if time_a > time_b else 1
    elif sort_mode == "added":
        time_a = game_a.extra.get("added_at", 0)
        time_b = game_b.extra.get("added_at", 0)
        if time_a != time_b:
            return -1 if time_a > time_b else 1
    elif sort_mode == "opened":
        count_a = config.play_count(game_a.id)
        count_b = config.play_count(game_b.id)
        if count_a != count_b:
            return -1 if count_a > count_b else 1
    key_a, key_b = game_a.sort_key, game_b.sort_key
    return -1 if key_a < key_b else (1 if key_a > key_b else 0)


def can_play_media(game) -> bool:
    if not plays_in_kabin(game):
        return False
    if game.source == "remote":
        return bool(game.extra.get("playable"))
    return playable_file(game) is not None


def can_read_remote(game) -> bool:
    """A paired host marked this book/comic playable and Kabin can read it.

    Older hosts advertised every book file as playable, including MOBI/AZW3
    that only open via xdg-open. Refusing those here stops a fetch that
    would only fail after downloading the whole file.
    """
    if getattr(game, "source", "") != "remote":
        return False
    if kind_for(game).id not in READABLE_KINDS:
        return False
    if not (getattr(game, "extra", None) or {}).get("playable"):
        return False
    return reader_backend_for(game) is not None


def opens_reader(game) -> bool:
    return opens_in_kabin_reader(game) or can_read_remote(game)


def reader_progress_targets(item, games) -> list[tuple[dict, str]]:
    """(host, catalog_id) pairs that should receive this item's page progress."""
    extra = getattr(item, "extra", None) or {}
    if getattr(item, "source", "") == "remote":
        host = extra.get("host") or {}
        remote_id = extra.get("remote_id") or ""
        if host.get("token") and remote_id:
            return [(host, remote_id)]
        return []
    targets = []
    seen = set()
    for game in games or []:
        if getattr(game, "source", "") != "remote":
            continue
        if (game.extra.get("remote_id") or "") != item.id:
            continue
        host = game.extra.get("host") or {}
        token = host.get("token")
        if not token:
            continue
        key = (host.get("address"), host.get("port"), token)
        if key in seen:
            continue
        seen.add(key)
        targets.append((host, item.id))
    return targets


def queue_for(game) -> list[dict]:
    if game.source == "remote" and game.extra.get("playable"):
        host = game.extra.get("host") or {}
        remote_id = game.extra.get("remote_id", "")
        count = max(1, track_count(game))
        return [
            {
                "track": index,
                "title": game.title if count == 1 else f"{game.title} · {index + 1}",
                "uri": media_stream_url(host, remote_id, index),
            }
            for index in range(count)
        ]
    return local_queue(game)


def resume_hint(game, config) -> str:
    if opens_reader(game):
        page = resume_page(config, game.id)
        if page <= 0:
            return ""
        return f" Resume from page {page + 1}."
    total = track_count(game)
    if not should_resume(config, game.id, total):
        return ""
    track = resume_track(config, game.id, total)
    start = resume_seconds(config, game.id)
    if total > 1:
        place = f"track {track + 1}"
        if start:
            place += f", {format_clock(start)}"
        return f" Resume from {place}."
    if start:
        return f" Resume from {format_clock(start)}."
    return ""


def is_playing(game, playback_item) -> bool:
    return bool(game) and playback_item is game


def item_progress(game, config, *, is_current: bool, playback, playback_index: int, queue_length: int) -> float:
    """Fraction (0..1) through `game`, either live from an in-progress session or from saved resume state."""
    if not game:
        return 0
    if plays_in_kabin(game):
        if is_current and playback:
            duration = playback.duration
            frac = (playback.position / duration) if duration else 0
            total = max(1, queue_length)
            return min(1.0, (playback_index + max(0.0, frac)) / total)
        return progress_ratio(config, game.id, track_count(game))
    if opens_reader(game):
        return page_progress_ratio(config, game.id)
    return 0


def play_button_label(game, config, *, is_current: bool, playback) -> str:
    if is_current:
        return "Resume" if playback and playback.paused else "Pause"
    if plays_in_kabin(game) and should_resume(config, game.id, track_count(game)):
        return "Resume"
    if opens_reader(game) and resume_page(config, game.id) > 0:
        return "Resume"
    if game.source == "remote" and kind_for(game).id == "game":
        return "Stream"
    return kind_for(game).verb


def next_queue_index(index: int, queue_length: int, delta: int = 1) -> int | None:
    """Index to move to within the playback queue, or None if `delta` runs off either end."""
    target = index + delta
    return target if 0 <= target < queue_length else None


def related_items(item, games, *, limit: int = 12) -> list:
    """Other library items that share `item`'s series, ordered by series index.

    Series matching is case-insensitive on the already-parsed `series`
    field — titles.py fills that for books/comics, and remote catalog
    entries carry it through. Returns [] when there is no series or no
    siblings, so the details page can hide the row entirely.
    """
    series = (getattr(item, "series", None) or "").strip()
    if not series or limit <= 0:
        return []
    needle = series.casefold()
    item_id = getattr(item, "id", None)
    matches = []
    for game in games or []:
        if game is item:
            continue
        if item_id is not None and getattr(game, "id", None) == item_id:
            continue
        other = (getattr(game, "series", None) or "").strip()
        if other.casefold() != needle:
            continue
        matches.append(game)

    def sort_key(game):
        index = getattr(game, "series_index", None)
        title = getattr(game, "sort_key", None) or (getattr(game, "title", "") or "").casefold()
        if index is None:
            return (1, 0.0, title)
        try:
            return (0, float(index), title)
        except (TypeError, ValueError):
            return (1, 0.0, title)

    matches.sort(key=sort_key)
    return matches[:limit]


def local_path(item) -> Path | None:
    """The file or folder behind a local item, or None for Steam/remote/apps."""
    extra = getattr(item, "extra", None) or {}
    raw = extra.get("path")
    if not raw or getattr(item, "source", "") == "remote":
        return None
    return Path(raw)


def format_size(size: int) -> str:
    """'512 KB', '2.5 MB', '1.4 GB' - one decimal above KB, none below."""
    if size < 1024:
        return f"{size} B"
    value = float(size)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024
        if value < 1024 or unit == "TB":
            break
    if unit == "KB":
        return f"{value:.0f} {unit}"
    return f"{value:.1f}".rstrip("0").rstrip(".") + f" {unit}"


def file_details(item) -> list[str]:
    """Format and size for a file-backed item: ['SFC', '2.5 MB'].

    Folders (albums, series) report nothing rather than the size of one
    track. Items whose `media_format` already names the format (books,
    video) don't repeat it here; only the ROM suffix is new information."""
    path = local_path(item)
    if path is None:
        return []
    try:
        info = path.stat()
    except OSError:
        return []
    if not path.is_file():
        return []
    parts = []
    if getattr(item, "source", "") == "roms" and path.suffix:
        parts.append(path.suffix.lstrip(".").upper())
    parts.append(format_size(info.st_size))
    return parts


def rom_launch_summary(item, rom_dirs) -> str:
    """'Plays with mGBA.' for a ROM, from the console folder it came from."""
    if getattr(item, "source", "") != "roms":
        return ""
    path = local_path(item)
    if path is None:
        return ""
    for entry in rom_dirs or []:
        base = str(Path(entry.get("path", "")).expanduser())
        if not base or not str(path).startswith(base.rstrip("/") + "/"):
            continue
        emulator = entry.get("emulator")
        if isinstance(emulator, dict):
            name = str(emulator.get("name") or "").split(" · ")[0].strip()
            return f"Plays with {name}." if name else ""
        if isinstance(emulator, str) and emulator.strip():
            return f"Plays with a custom command: {emulator.split()[0]}."
        return ""
    return ""


def play_count_label(count: int) -> str:
    if count <= 1:
        return ""
    return f"{count} plays"


def empty_state_message(kind, value, title, media, category_count: int, host_status=None) -> tuple[str, str]:
    """Title/description for the library's no-matches status page.

    `category_count` must ignore search text and extra filters (favorites,
    unplayed, location) - it answers "is this category itself empty",
    which is a different question from "did this search/filter match
    anything". Conflating the two makes an unmatched search on a full
    library claim the library has nothing in it.
    """
    if kind == "type" and category_count == 0:
        return f"No {media.plural.lower()} yet", media.empty_hint
    if kind == "system" and category_count == 0:
        return (
            f"No {title} games found",
            "Add supported game files to this console library, then refresh Kabin.",
        )
    if kind == "host" and (host_status or {}).get("state") != "online":
        state = (host_status or {}).get("state")
        if state == "auth":
            return (
                "Pair with this host again",
                "Open Network & Hosts to pair again and verify this host's identity.",
            )
        if state == "checking":
            return (
                f"Checking {value}…",
                "Kabin is asking this host for its library.",
            )
        return (
            f"{value} is offline",
            "Check that Kabin Host is running on the other device, then use Refresh.",
        )
    return "No matches", "Try a different search, category, or filter."
