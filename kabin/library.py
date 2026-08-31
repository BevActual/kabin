"""Pure library filtering, sorting, and playability logic.

Extracted out of MainWindow so it can be tested without a live GTK window.
"""
from __future__ import annotations

from .kinds import kind_for
from .network import media_stream_url
from .playback import (
    format_clock,
    local_queue,
    playable_file,
    plays_in_kabin,
    progress_ratio,
    resume_seconds,
    resume_track,
    should_resume,
    track_count,
)


def matches_context(game, search_text: str, category, config) -> bool:
    if search_text and search_text not in game.search_text:
        return False
    kind, value = category
    if kind in ("home", "all"):
        return True
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
    if not game or not plays_in_kabin(game):
        return 0
    if is_current and playback:
        duration = playback.duration
        frac = (playback.position / duration) if duration else 0
        total = max(1, queue_length)
        return min(1.0, (playback_index + max(0.0, frac)) / total)
    return progress_ratio(config, game.id, track_count(game))


def play_button_label(game, config, *, is_current: bool, playback) -> str:
    if is_current:
        return "Resume" if playback and playback.paused else "Pause"
    if plays_in_kabin(game) and should_resume(config, game.id, track_count(game)):
        return "Resume"
    if game.source == "remote" and kind_for(game).id == "game":
        return "Stream"
    return kind_for(game).verb


def next_queue_index(index: int, queue_length: int, delta: int = 1) -> int | None:
    """Index to move to within the playback queue, or None if `delta` runs off either end."""
    target = index + delta
    return target if 0 <= target < queue_length else None
