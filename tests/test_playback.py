import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from kabin.config import Config
from kabin.playback import (
    adopt_progress,
    format_clock,
    is_safe_media_file,
    local_queue,
    playable_file,
    playable_tracks,
    plays_in_kabin,
    progress_for,
    progress_ratio,
    resume_seconds,
    resume_track,
    save_progress,
    should_resume,
)


class TestPlayback(unittest.TestCase):
    def test_resume_skips_short_and_finished_positions(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            save_progress(config, "video:1", 4, 100)
            self.assertEqual(resume_seconds(config, "video:1"), 0)
            save_progress(config, "video:1", 91, 100)
            self.assertEqual(resume_seconds(config, "video:1"), 0)
            save_progress(config, "video:1", 40, 100)
            self.assertEqual(resume_seconds(config, "video:1"), 40)
            save_progress(config, "music:1", 12, 200, track=2)
            self.assertEqual(resume_track(config, "music:1", 5), 2)
            self.assertTrue(should_resume(config, "music:1", 5))
            save_progress(config, "music:1", 190, 200, track=4)
            self.assertEqual(resume_track(config, "music:1", 5), 0)
            restored = Config(path=Path(tmp) / "config.json")
            self.assertEqual(progress_for(restored, "video:1")["position"], 40)
            self.assertGreater(progress_for(restored, "video:1")["updated_at"], 0)
            self.assertLessEqual(progress_for(restored, "video:1")["updated_at"], time.time())

    def test_playable_file_uses_first_album_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            (album / "b.flac").write_bytes(b"b")
            (album / "a.flac").write_bytes(b"a")
            item = SimpleNamespace(extra={"path": str(album)}, media_type="music")
            (album / "cover.jpg").write_bytes(b"art")
            self.assertTrue(plays_in_kabin(item))
            self.assertEqual(playable_tracks(item), [album / "a.flac", album / "b.flac"])
            self.assertEqual(playable_file(item), album / "a.flac")
            self.assertEqual(local_queue(item)[0]["title"], "a")
            (album / "Artist - Album - 02 Late.flac").write_bytes(b"c")
            (album / "Artist - Album - 01 Early.flac").write_bytes(b"d")
            numbered = SimpleNamespace(
                extra={"path": str(album)},
                media_type="music",
                title="Album",
                creators=["Artist"],
            )
            queue = local_queue(numbered)
            self.assertEqual([entry["title"] for entry in queue[:2]], ["Early", "Late"])

    def test_safe_media_file_stays_inside_configured_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "films"
            library.mkdir()
            inside = library / "film.mkv"
            inside.write_bytes(b"ok")
            outside = Path(tmp) / "secret.mkv"
            outside.write_bytes(b"no")
            link = library / "escape.mkv"
            link.symlink_to(outside)
            dirs = [{"path": str(library), "media_type": "video"}]
            self.assertTrue(is_safe_media_file(inside, dirs))
            self.assertFalse(is_safe_media_file(outside, dirs))
            self.assertFalse(is_safe_media_file(link, dirs))
            self.assertFalse(is_safe_media_file(inside, [{"path": "", "media_type": "video"}]))

    def test_adopt_progress_keeps_the_newer_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            save_progress(config, "video:1", 10, 100)
            older = {"position": 80, "duration": 100, "track": 0, "updated_at": 1}
            self.assertFalse(adopt_progress(config, "video:1", older))
            self.assertEqual(progress_for(config, "video:1")["position"], 10)
            newer = {
                "position": 55,
                "duration": 100,
                "track": 0,
                "updated_at": time.time() + 10,
            }
            self.assertTrue(adopt_progress(config, "video:1", newer))
            self.assertEqual(progress_for(config, "video:1")["position"], 55)

    def test_progress_ratio_hides_finished_and_short_starts(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            save_progress(config, "video:1", 4, 100)
            self.assertEqual(progress_ratio(config, "video:1"), 0)
            save_progress(config, "video:1", 40, 100)
            self.assertAlmostEqual(progress_ratio(config, "video:1"), 0.4)
            save_progress(config, "video:1", 95, 100)
            self.assertEqual(progress_ratio(config, "video:1"), 0)
            save_progress(config, "music:1", 60, 200, track=1)
            self.assertAlmostEqual(progress_ratio(config, "music:1", 4), 0.325)

    def test_format_clock(self):
        self.assertEqual(format_clock(75), "1:15")
        self.assertEqual(format_clock(3661), "1:01:01")


if __name__ == "__main__":
    unittest.main()
