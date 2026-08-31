import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from kabin.config import Config
from kabin.library import (
    can_play_media,
    compare_items,
    is_playing,
    item_progress,
    matches,
    matches_context,
    next_queue_index,
    play_button_label,
    queue_for,
    resume_hint,
)
from kabin.playback import save_progress


def _game(item_id, source="steam", subtitle="", media_type="game", title="", extra=None):
    return SimpleNamespace(
        id=item_id,
        title=title or item_id,
        source=source,
        subtitle=subtitle,
        media_type=media_type,
        extra=extra or {},
        search_text=f"{title or item_id} {subtitle} {source}".casefold(),
        sort_key=(title or item_id).casefold(),
    )


class TestMatchesContext(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config = Config(path=Path(self._tmp.name) / "config.json")

    def test_search_text_filters(self):
        game = _game("g1", title="Portal 2")
        self.assertTrue(matches_context(game, "portal", ("home", None), self.config))
        self.assertFalse(matches_context(game, "halo", ("home", None), self.config))

    def test_home_and_all_categories_pass_everything(self):
        game = _game("g1")
        self.assertTrue(matches_context(game, "", ("home", None), self.config))
        self.assertTrue(matches_context(game, "", ("all", None), self.config))

    def test_type_category_matches_media_kind(self):
        game = _game("g1", media_type="music")
        self.assertTrue(matches_context(game, "", ("type", "music"), self.config))
        self.assertFalse(matches_context(game, "", ("type", "video"), self.config))

    def test_unplayed_preset_excludes_recently_played(self):
        game = _game("g1")
        self.assertTrue(matches_context(game, "", ("preset", "unplayed"), self.config))
        self.config.recent[game.id] = 1.0
        self.assertFalse(matches_context(game, "", ("preset", "unplayed"), self.config))

    def test_favorite_category_checks_config(self):
        game = _game("g1")
        self.assertFalse(matches_context(game, "", ("favorite", None), self.config))
        self.config.toggle_favorite(game.id)
        self.assertTrue(matches_context(game, "", ("favorite", None), self.config))

    def test_source_category(self):
        game = _game("g1", source="steam")
        self.assertTrue(matches_context(game, "", ("source", "steam"), self.config))
        self.assertFalse(matches_context(game, "", ("source", "roms"), self.config))

    def test_system_category_requires_roms_source(self):
        game = _game("g1", source="roms", subtitle="snes")
        self.assertTrue(matches_context(game, "", ("system", "snes"), self.config))
        self.assertFalse(matches_context(game, "", ("system", "nes"), self.config))
        other_source = _game("g2", source="steam", subtitle="snes")
        self.assertFalse(matches_context(other_source, "", ("system", "snes"), self.config))

    def test_host_category_requires_remote_source(self):
        game = _game("g1", source="remote", subtitle="living-room")
        self.assertTrue(matches_context(game, "", ("host", "living-room"), self.config))
        self.assertFalse(matches_context(game, "", ("host", "bedroom"), self.config))


class TestMatches(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config = Config(path=Path(self._tmp.name) / "config.json")

    def test_favorites_only_excludes_non_favorites(self):
        game = _game("g1")
        self.assertFalse(
            matches(game, "", ("home", None), self.config, favorites_only=True)
        )
        self.config.toggle_favorite(game.id)
        self.assertTrue(
            matches(game, "", ("home", None), self.config, favorites_only=True)
        )

    def test_unplayed_only_excludes_played(self):
        game = _game("g1")
        self.config.recent[game.id] = 1.0
        self.assertFalse(
            matches(game, "", ("home", None), self.config, unplayed_only=True)
        )

    def test_location_filter_local_and_remote(self):
        local_game = _game("g1", source="steam")
        remote_game = _game("g2", source="remote")
        self.assertTrue(
            matches(local_game, "", ("home", None), self.config, location_filter="local")
        )
        self.assertFalse(
            matches(remote_game, "", ("home", None), self.config, location_filter="local")
        )
        self.assertTrue(
            matches(remote_game, "", ("home", None), self.config, location_filter="remote")
        )
        self.assertFalse(
            matches(local_game, "", ("home", None), self.config, location_filter="remote")
        )

    def test_falls_through_to_context_failure(self):
        game = _game("g1", title="Portal")
        self.assertFalse(matches(game, "halo", ("home", None), self.config))


class TestCompareItems(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config = Config(path=Path(self._tmp.name) / "config.json")

    def test_recent_sort_orders_newest_first(self):
        older = _game("a", title="Zebra")
        newer = _game("b", title="Apple")
        self.config.recent[older.id] = 1.0
        self.config.recent[newer.id] = 2.0
        self.assertEqual(compare_items(newer, older, "recent", self.config), -1)
        self.assertEqual(compare_items(older, newer, "recent", self.config), 1)

    def test_added_sort_orders_newest_first(self):
        older = _game("a", extra={"added_at": 1})
        newer = _game("b", extra={"added_at": 2})
        self.assertEqual(compare_items(newer, older, "added", self.config), -1)

    def test_falls_back_to_alphabetical_sort_key(self):
        a = _game("a", title="Apple")
        b = _game("b", title="Banana")
        self.assertEqual(compare_items(a, b, "title", self.config), -1)
        self.assertEqual(compare_items(b, a, "title", self.config), 1)
        self.assertEqual(compare_items(a, a, "title", self.config), 0)

    def test_ties_fall_through_to_alphabetical(self):
        a = _game("a", title="Apple", extra={"added_at": 5})
        b = _game("b", title="Banana", extra={"added_at": 5})
        self.assertEqual(compare_items(a, b, "added", self.config), -1)


class TestCanPlayMediaAndQueue(unittest.TestCase):
    def test_non_media_kind_cannot_play(self):
        game = _game("g1", media_type="game")
        self.assertFalse(can_play_media(game))

    def test_remote_media_requires_playable_flag(self):
        not_playable = _game("g1", source="remote", media_type="video")
        self.assertFalse(can_play_media(not_playable))
        playable = _game("g2", source="remote", media_type="video", extra={"playable": True})
        self.assertTrue(can_play_media(playable))

    def test_local_media_requires_a_resolvable_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "movie.mkv"
            video_path.write_bytes(b"data")
            game = _game("g1", media_type="video", extra={"path": str(video_path)})
            self.assertTrue(can_play_media(game))
            missing = _game("g2", media_type="video", extra={"path": str(Path(tmp) / "gone.mkv")})
            self.assertFalse(can_play_media(missing))

    def test_queue_for_remote_playable_builds_stream_urls(self):
        game = _game(
            "g1",
            source="remote",
            media_type="music",
            title="Album",
            extra={
                "playable": True,
                "track_count": 2,
                "remote_id": "abc",
                "host": {"address": "kabin.local", "port": 42424},
            },
        )
        queue = queue_for(game)
        self.assertEqual(len(queue), 2)
        self.assertEqual(queue[0]["track"], 0)
        self.assertIn("id=abc", queue[0]["uri"])
        self.assertIn("track=1", queue[1]["uri"])

    def test_queue_for_local_delegates_to_local_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            track = Path(tmp) / "01 Song.flac"
            track.write_bytes(b"data")
            game = _game("g1", media_type="music", title="Album", extra={"path": str(Path(tmp))})
            queue = queue_for(game)
            self.assertEqual(len(queue), 1)
            self.assertTrue(queue[0]["uri"].startswith("file://"))


class TestResumeHint(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config = Config(path=Path(self._tmp.name) / "config.json")

    def test_no_progress_gives_no_hint(self):
        game = _game("g1", media_type="video")
        self.assertEqual(resume_hint(game, self.config), "")

    def test_single_track_hint_includes_clock(self):
        game = _game("g1", media_type="video")
        save_progress(self.config, game.id, 40, 100)
        self.assertEqual(resume_hint(game, self.config), " Resume from 0:40.")

    def test_multi_track_hint_includes_track_number(self):
        game = _game("g1", media_type="music", extra={"track_count": 5})
        save_progress(self.config, game.id, 12, 200, track=2)
        self.assertEqual(resume_hint(game, self.config), " Resume from track 3, 0:12.")


class TestIsPlaying(unittest.TestCase):
    def test_true_only_when_item_is_the_playback_item(self):
        game = _game("g1")
        other = _game("g2")
        self.assertTrue(is_playing(game, game))
        self.assertFalse(is_playing(game, other))
        self.assertFalse(is_playing(game, None))
        self.assertFalse(is_playing(None, None))


class TestItemProgress(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config = Config(path=Path(self._tmp.name) / "config.json")

    def test_non_media_kind_has_no_progress(self):
        game = _game("g1", media_type="game")
        self.assertEqual(
            item_progress(game, self.config, is_current=False, playback=None, playback_index=0, queue_length=1),
            0,
        )

    def test_not_current_falls_back_to_saved_progress(self):
        game = _game("g1", media_type="video")
        save_progress(self.config, game.id, 40, 100)
        self.assertAlmostEqual(
            item_progress(game, self.config, is_current=False, playback=None, playback_index=0, queue_length=1),
            0.4,
        )

    def test_current_session_uses_live_position_within_queue(self):
        game = _game("g1", media_type="music")
        playback = SimpleNamespace(position=50, duration=100)
        # Second track (index 1) of 4, half-way through -> (1 + 0.5) / 4
        ratio = item_progress(
            game, self.config, is_current=True, playback=playback, playback_index=1, queue_length=4
        )
        self.assertAlmostEqual(ratio, 0.375)

    def test_current_session_clamps_to_one(self):
        game = _game("g1", media_type="video")
        playback = SimpleNamespace(position=999, duration=100)
        ratio = item_progress(
            game, self.config, is_current=True, playback=playback, playback_index=0, queue_length=1
        )
        self.assertEqual(ratio, 1.0)

    def test_current_but_no_playback_session_falls_back_to_saved(self):
        game = _game("g1", media_type="video")
        save_progress(self.config, game.id, 40, 100)
        ratio = item_progress(
            game, self.config, is_current=True, playback=None, playback_index=0, queue_length=1
        )
        self.assertAlmostEqual(ratio, 0.4)

    def test_zero_duration_treated_as_no_progress_within_queue_slot(self):
        game = _game("g1", media_type="video")
        playback = SimpleNamespace(position=0, duration=0)
        ratio = item_progress(
            game, self.config, is_current=True, playback=playback, playback_index=2, queue_length=4
        )
        self.assertAlmostEqual(ratio, 0.5)


class TestPlayButtonLabel(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config = Config(path=Path(self._tmp.name) / "config.json")

    def test_current_and_paused_offers_resume(self):
        game = _game("g1", media_type="video")
        playback = SimpleNamespace(paused=True)
        self.assertEqual(
            play_button_label(game, self.config, is_current=True, playback=playback), "Resume"
        )

    def test_current_and_playing_offers_pause(self):
        game = _game("g1", media_type="video")
        playback = SimpleNamespace(paused=False)
        self.assertEqual(
            play_button_label(game, self.config, is_current=True, playback=playback), "Pause"
        )

    def test_current_with_no_playback_session_offers_pause(self):
        game = _game("g1", media_type="video")
        self.assertEqual(
            play_button_label(game, self.config, is_current=True, playback=None), "Pause"
        )

    def test_not_current_with_saved_progress_offers_resume(self):
        game = _game("g1", media_type="video")
        save_progress(self.config, game.id, 40, 100)
        self.assertEqual(
            play_button_label(game, self.config, is_current=False, playback=None), "Resume"
        )

    def test_remote_game_offers_stream(self):
        game = _game("g1", source="remote", media_type="game")
        self.assertEqual(
            play_button_label(game, self.config, is_current=False, playback=None), "Stream"
        )

    def test_default_falls_back_to_kind_verb(self):
        game = _game("g1", source="steam", media_type="game")
        self.assertEqual(
            play_button_label(game, self.config, is_current=False, playback=None), "Play"
        )


class TestNextQueueIndex(unittest.TestCase):
    def test_advances_by_one_within_bounds(self):
        self.assertEqual(next_queue_index(0, 3), 1)
        self.assertEqual(next_queue_index(1, 3), 2)

    def test_none_past_the_last_track(self):
        self.assertIsNone(next_queue_index(2, 3))

    def test_none_before_the_first_track(self):
        self.assertIsNone(next_queue_index(0, 3, delta=-1))

    def test_steps_backward_within_bounds(self):
        self.assertEqual(next_queue_index(2, 3, delta=-1), 1)

    def test_empty_queue_is_always_out_of_range(self):
        self.assertIsNone(next_queue_index(0, 0))


if __name__ == "__main__":
    unittest.main()
