from __future__ import annotations

import time
from pathlib import Path

from .kinds import kind_for
from .streaming import native_helper_path
from .titles import clean_track_title, track_sort_key

PLAY_IN_KABIN = frozenset({"video", "music"})
RESUME_AFTER = 5
FINISHED_RATIO = 0.9


def plays_in_kabin(item) -> bool:
    return kind_for(item).id in PLAY_IN_KABIN


def progress_map(config) -> dict:
    return config.data.setdefault("progress", {})


def progress_for(config, item_id: str) -> dict:
    raw = progress_map(config).get(item_id) or {}
    return {
        "position": float(raw.get("position") or 0),
        "duration": float(raw.get("duration") or 0),
        "track": int(raw.get("track") or 0),
        "updated_at": float(raw.get("updated_at") or 0),
    }


def public_progress(info: dict) -> dict:
    return {
        "position": float(info.get("position") or 0),
        "duration": float(info.get("duration") or 0),
        "track": int(info.get("track") or 0),
        "updated_at": float(info.get("updated_at") or 0),
    }


def save_progress(config, item_id: str, position: float, duration: float = 0, track: int = 0) -> None:
    progress_map(config)[item_id] = {
        "position": max(0.0, float(position)),
        "duration": max(0.0, float(duration)),
        "track": max(0, int(track)),
        "updated_at": time.time(),
    }
    config.save()


def adopt_progress(config, item_id: str, payload, save: bool = True) -> bool:
    """Take `payload` as this item's progress if it's newer than ours.

    Pass save=False when adopting several items in a row (a library
    refresh syncing every book from a paired host) and save once after,
    instead of writing the whole config per item.
    """
    if not payload:
        return False
    incoming = public_progress(payload)
    if incoming["updated_at"] <= progress_for(config, item_id)["updated_at"]:
        return False
    progress_map(config)[item_id] = incoming
    if save:
        config.save()
    return True


def resume_seconds(config, item_id: str) -> float:
    info = progress_for(config, item_id)
    duration = info["duration"]
    position = info["position"]
    if position < RESUME_AFTER:
        return 0
    if duration and position >= duration * FINISHED_RATIO:
        return 0
    return position


def resume_track(config, item_id: str, track_total: int = 1) -> int:
    info = progress_for(config, item_id)
    track = info["track"]
    total = max(1, int(track_total or 1))
    if track <= 0:
        return 0
    if track >= total:
        return 0
    if track == total - 1 and info["duration"] and info["position"] >= info["duration"] * FINISHED_RATIO:
        return 0
    return track


def should_resume(config, item_id: str, track_total: int = 1) -> bool:
    return resume_seconds(config, item_id) > 0 or resume_track(config, item_id, track_total) > 0


def progress_ratio(config, item_id: str, track_total: int = 1) -> float:
    """0–1 watched/listened amount for poster ticks. Finished titles return 0."""
    info = progress_for(config, item_id)
    total = max(1, int(track_total or 1))
    duration = info["duration"]
    position = info["position"]
    track = max(0, min(info["track"], total - 1))
    if total > 1:
        frac = (position / duration) if duration else 0
        ratio = (track + min(1.0, max(0.0, frac))) / total
        if ratio >= FINISHED_RATIO:
            return 0
        return ratio if track or position >= RESUME_AFTER else 0
    if position < RESUME_AFTER:
        return 0
    if not duration:
        return 0
    if position >= duration * FINISHED_RATIO:
        return 0
    return min(1.0, position / duration)


def playable_tracks(item) -> list[Path]:
    raw = (getattr(item, "extra", None) or {}).get("path")
    if not raw:
        return []
    path = Path(raw).expanduser()
    kind = kind_for(item)
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    tracks = []
    for child in path.iterdir():
        if child.name.startswith(".") or child.is_symlink() or not child.is_file():
            continue
        if kind.extensions and child.suffix.lower() not in kind.extensions:
            continue
        tracks.append(child)
    tracks.sort(key=track_sort_key)
    return tracks


def playable_file(item) -> Path | None:
    tracks = playable_tracks(item)
    return tracks[0] if tracks else None


def track_count(item) -> int:
    extra = getattr(item, "extra", None) or {}
    if extra.get("track_count"):
        try:
            return max(1, int(extra["track_count"]))
        except (TypeError, ValueError):
            pass
    tracks = playable_tracks(item)
    return len(tracks) if tracks else (1 if plays_in_kabin(item) else 0)


def local_queue(item) -> list[dict]:
    tracks = playable_tracks(item)
    creators = getattr(item, "creators", None) or []
    artist = creators[0] if creators else ""
    album = getattr(item, "title", "") or ""
    return [
        {
            "track": index,
            "title": clean_track_title(path.name, album=album, artist=artist),
            "uri": path.resolve().as_uri(),
        }
        for index, path in enumerate(tracks)
    ]


def format_clock(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def is_safe_media_file(path: Path, media_dirs) -> bool:
    try:
        if path.is_symlink() or not path.is_file():
            return False
        resolved = path.resolve()
    except OSError:
        return False
    for entry in media_dirs or []:
        raw_root = (entry.get("path") or "").strip()
        if not raw_root:
            continue
        root = Path(raw_root).expanduser()
        try:
            if resolved.is_relative_to(root.resolve()) and not resolved.is_symlink():
                return True
        except (OSError, ValueError):
            continue
    return False


def helper_ready() -> bool:
    return native_helper_path() is not None
