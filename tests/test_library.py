import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

from kabin.config import Config
from kabin.kinds import get_kind
from kabin.library import (
    can_play_media,
    can_read_remote,
    compare_items,
    empty_state_message,
    is_playing,
    item_progress,
    matches,
    matches_context,
    next_queue_index,
    play_button_label,
    queue_for,
    reader_progress_targets,
    related_items,
    resume_hint,
)
from kabin.playback import save_progress


def _cbz(tmp_dir) -> Path:
    path = Path(tmp_dir) / "issue.cbz"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("1.jpg", b"a")
    return path


def _game(
    item_id,
    source="steam",
    subtitle="",
    media_type="game",
    title="",
    extra=None,
    series="",
    series_index=None,
    media_format="",
):
    return SimpleNamespace(
        id=item_id,
        title=title or item_id,
        source=source,
        subtitle=subtitle,
        media_type=media_type,
        extra=extra or {},
        series=series,
        series_index=series_index,
        media_format=media_format,
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

    def test_remote_mobi_is_not_readable_even_when_host_marks_playable(self):
        # Older hosts advertised every book file as playable. A MOBI still
        # must not offer in-app Read — there is no Kabin backend for it.
        ready = _game(
            "remote:den:book:novel.mobi",
            source="remote",
            media_type="book",
            media_format="mobi",
            extra={"playable": True, "remote_id": "book:novel.mobi"},
        )
        # media_format may live on the object; also stash on extra for safety
        ready.media_format = "mobi"
        self.assertFalse(can_read_remote(ready))

    def test_remote_book_is_readable_when_host_marks_it_playable(self):
        ghost = _game("remote:den:book:novel.epub", source="remote", media_type="book")
        self.assertFalse(can_read_remote(ghost))
        ready = _game(
            "remote:den:book:novel.epub",
            source="remote",
            media_type="book",
            extra={"playable": True},
        )
        self.assertTrue(can_read_remote(ready))
        self.assertFalse(can_play_media(ready))

    def test_reader_progress_targets_local_copy_and_remote_item(self):
        host = {"address": "10.0.0.2", "port": 42424, "token": "abc"}
        local = _game("book:novel.epub", media_type="book")
        remote = _game(
            "remote:den:book:novel.epub",
            source="remote",
            media_type="book",
            extra={"host": host, "remote_id": "book:novel.epub", "playable": True},
        )
        self.assertEqual(reader_progress_targets(local, [local, remote]), [(host, "book:novel.epub")])
        self.assertEqual(reader_progress_targets(remote, [local, remote]), [(host, "book:novel.epub")])
        self.assertEqual(reader_progress_targets(local, [local]), [])

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

    def test_reader_item_hint_uses_page_wording_not_a_clock(self):
        cbz = _cbz(self._tmp.name)
        game = _game("c1", media_type="comic", extra={"path": str(cbz)})
        save_progress(self.config, game.id, 41, 100)
        self.assertEqual(resume_hint(game, self.config), " Resume from page 42.")
        self.assertNotIn("0:41", resume_hint(game, self.config))


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

    def test_reader_item_falls_back_to_saved_page_progress(self):
        cbz = _cbz(self._tmp.name)
        game = _game("c1", media_type="comic", extra={"path": str(cbz)})
        save_progress(self.config, game.id, 40, 100)
        ratio = item_progress(
            game, self.config, is_current=False, playback=None, playback_index=0, queue_length=1
        )
        self.assertAlmostEqual(ratio, 0.4)

    def test_reader_item_shows_progress_on_early_pages(self):
        cbz = _cbz(self._tmp.name)
        game = _game("c1", media_type="comic", extra={"path": str(cbz)})
        save_progress(self.config, game.id, 3, 100)
        ratio = item_progress(
            game, self.config, is_current=False, playback=None, playback_index=0, queue_length=1
        )
        self.assertAlmostEqual(ratio, 0.03)


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

    def test_reader_item_with_saved_page_offers_resume(self):
        cbz = _cbz(self._tmp.name)
        game = _game("c1", media_type="comic", extra={"path": str(cbz)})
        self.assertEqual(
            play_button_label(game, self.config, is_current=False, playback=None), "Read"
        )
        save_progress(self.config, game.id, 5, 20)
        self.assertEqual(
            play_button_label(game, self.config, is_current=False, playback=None), "Resume"
        )

    def test_remote_playable_book_offers_read(self):
        game = _game(
            "remote:den:book:novel.epub",
            source="remote",
            media_type="book",
            extra={"playable": True},
        )
        self.assertEqual(
            play_button_label(game, self.config, is_current=False, playback=None), "Read"
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


class TestEmptyStateMessage(unittest.TestCase):
    def test_genuinely_empty_type_category_invites_adding_content(self):
        game_kind = get_kind("game")
        title, description = empty_state_message("type", "game", "Games", game_kind, 0)
        self.assertEqual(title, "No games yet")
        self.assertEqual(description, game_kind.empty_hint)

    def test_unmatched_search_on_a_nonempty_library_is_not_reported_as_empty(self):
        # Regression: this used to be driven by the post-search/post-filter
        # count, so searching for something nobody owns claimed the whole
        # library had nothing in it instead of just this search.
        game_kind = get_kind("game")
        title, description = empty_state_message("type", "game", "Games", game_kind, 12)
        self.assertEqual(title, "No matches")
        self.assertEqual(description, "Try a different search, category, or filter.")

    def test_genuinely_empty_system_category(self):
        title, _description = empty_state_message("system", None, "Nintendo 64", None, 0)
        self.assertEqual(title, "No Nintendo 64 games found")

    def test_unmatched_search_on_a_nonempty_system_category(self):
        title, _description = empty_state_message("system", None, "Nintendo 64", None, 6)
        self.assertEqual(title, "No matches")

    def test_offline_host(self):
        title, description = empty_state_message(
            "host", "Living Room", "Living Room", None, 3, {"state": "offline"}
        )
        self.assertEqual(title, "Living Room is offline")
        self.assertIn("Refresh", description)

    def test_host_needing_reauthorization(self):
        title, description = empty_state_message(
            "host", "Living Room", "Living Room", None, 3, {"state": "auth"}
        )
        self.assertEqual(title, "Pair with this host again")
        self.assertIn("pair again", description)

    def test_online_host_falls_through_to_default(self):
        title, _description = empty_state_message(
            "host", "Living Room", "Living Room", None, 0, {"state": "online"}
        )
        self.assertEqual(title, "No matches")

    def test_host_with_no_status_yet_is_treated_as_offline(self):
        title, _description = empty_state_message("host", "Living Room", "Living Room", None, 3, None)
        self.assertEqual(title, "Living Room is offline")

    def test_favorites_and_other_categories_use_the_generic_message(self):
        title, description = empty_state_message("favorite", None, "Favorites", None, 0)
        self.assertEqual(title, "No matches")
        self.assertEqual(description, "Try a different search, category, or filter.")



class TestRelatedItems(unittest.TestCase):
    def test_empty_without_series_or_siblings(self):
        lone = _game("b1", media_type="book", title="Standalone", series="")
        self.assertEqual(related_items(lone, [lone]), [])
        series_of_one = _game("b2", media_type="book", title="Only One", series="Lonely")
        self.assertEqual(related_items(series_of_one, [series_of_one]), [])

    def test_orders_by_series_index_and_skips_self(self):
        one = _game("b1", media_type="book", title="Stone", series="Harry Potter", series_index=1)
        three = _game("b3", media_type="book", title="Azkaban", series="Harry Potter", series_index=3)
        two = _game("b2", media_type="book", title="Chamber", series="harry potter", series_index=2)
        other = _game("b9", media_type="book", title="Unrelated", series="Discworld", series_index=1)
        related = related_items(two, [one, two, three, other])
        self.assertEqual([item.id for item in related], ["b1", "b3"])

    def test_unindexed_siblings_sort_after_numbered_ones(self):
        numbered = _game("c1", media_type="comic", title="Vol 1", series="Naruto", series_index=1)
        extra = _game("c0", media_type="comic", title="Artbook", series="Naruto")
        related = related_items(numbered, [extra, numbered])
        self.assertEqual([item.id for item in related], ["c0"])



if __name__ == "__main__":
    unittest.main()
