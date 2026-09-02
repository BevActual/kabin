import tempfile
import unittest
from pathlib import Path

from kabin.config import Config
from kabin.sessions import (
    MIN_RECORDED_SECONDS,
    QUICK_EXIT_SECONDS,
    PlaySession,
    format_play_time,
    quick_failure_message,
    recordable_seconds,
)


class _FakeProcess:
    def __init__(self, returncode=None):
        self.returncode = returncode

    def poll(self):
        return self.returncode


class TestPlaySession(unittest.TestCase):
    def test_session_follows_the_process(self):
        process = _FakeProcess()
        session = PlaySession("roms:gba:x", "Game", process, started_at=100.0)
        self.assertTrue(session.running)
        self.assertEqual(session.elapsed(now=160.0), 60.0)
        process.returncode = 0
        self.assertFalse(session.running)
        self.assertEqual(session.returncode(), 0)

    def test_quick_non_zero_exit_is_called_out(self):
        message = quick_failure_message("Game", 1, 0.4)
        self.assertIn("closed right away", message)
        self.assertIn("exit code 1", message)
        self.assertIn("Settings", message)

    def test_quick_signal_death_names_the_signal(self):
        self.assertIn("signal 11", quick_failure_message("Game", -11, 0.4))

    def test_clean_or_long_exits_are_not_errors(self):
        # Some emulators fork and return 0 immediately; a user quitting a
        # game after an hour is just done playing.
        self.assertIsNone(quick_failure_message("Game", 0, 0.1))
        self.assertIsNone(quick_failure_message("Game", 1, QUICK_EXIT_SECONDS))
        self.assertIsNone(quick_failure_message("Game", 1, 3600))
        self.assertIsNone(quick_failure_message("Game", None, 0.1))

    def test_only_real_sessions_count_as_play_time(self):
        self.assertEqual(recordable_seconds(MIN_RECORDED_SECONDS - 1), 0)
        self.assertEqual(recordable_seconds(MIN_RECORDED_SECONDS), int(MIN_RECORDED_SECONDS))
        self.assertEqual(recordable_seconds(3599.9), 3599)

    def test_play_time_formatting(self):
        self.assertEqual(format_play_time(0), "")
        self.assertEqual(format_play_time(59), "")
        self.assertEqual(format_play_time(60), "1m")
        self.assertEqual(format_play_time(42 * 60), "42m")
        self.assertEqual(format_play_time(3600), "1h")
        self.assertEqual(format_play_time(3 * 3600 + 5 * 60), "3h 05m")


class TestConfigPlayTime(unittest.TestCase):
    def test_play_time_accumulates_and_ignores_empty_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            self.assertEqual(config.play_seconds("roms:gba:x"), 0)
            config.record_play_time("roms:gba:x", 90)
            config.record_play_time("roms:gba:x", 0)
            config.record_play_time("roms:gba:x", 30)
            self.assertEqual(config.play_seconds("roms:gba:x"), 120)

            reloaded = Config(path=Path(tmp) / "config.json")
            self.assertEqual(reloaded.play_seconds("roms:gba:x"), 120)


if __name__ == "__main__":
    unittest.main()
