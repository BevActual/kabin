import tempfile
import unittest
from pathlib import Path

from omagames.sources import roms


class TestGetGames(unittest.TestCase):
    def test_scans_matching_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "Chrono Trigger.sfc").write_bytes(b"")
            (base / "Super Metroid.sfc").write_bytes(b"")
            (base / "readme.txt").write_bytes(b"")

            config = [
                {
                    "path": str(base),
                    "system": "SNES",
                    "extensions": ["sfc"],
                    "emulator": "retroarch -L core.so {rom}",
                }
            ]
            games = roms.get_games(config)
            titles = sorted(g.title for g in games)
            self.assertEqual(titles, ["Chrono Trigger", "Super Metroid"])
            self.assertTrue(all(g.source == "roms" for g in games))
            self.assertTrue(all(g.subtitle == "SNES" for g in games))

    def test_skips_entry_without_rom_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "game.sfc").write_bytes(b"")
            config = [
                {
                    "path": str(base),
                    "system": "SNES",
                    "extensions": ["sfc"],
                    "emulator": "retroarch -L core.so",
                }
            ]
            self.assertEqual(roms.get_games(config), [])

    def test_skips_missing_directory(self):
        config = [
            {
                "path": "/nonexistent/roms",
                "system": "SNES",
                "extensions": ["sfc"],
                "emulator": "retroarch {rom}",
            }
        ]
        self.assertEqual(roms.get_games(config), [])

    def test_respects_hidden_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "game.sfc").write_bytes(b"")
            config = [
                {
                    "path": str(base),
                    "system": "SNES",
                    "extensions": ["sfc"],
                    "emulator": "retroarch {rom}",
                }
            ]
            games = roms.get_games(config, hidden_ids={"roms:SNES:game.sfc"})
            self.assertEqual(games, [])

    def test_launch_builds_command_with_rom_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            rom = base / "game.sfc"
            rom.write_bytes(b"")
            config = [
                {
                    "path": str(base),
                    "system": "SNES",
                    "extensions": ["sfc"],
                    "emulator": "echo {rom}",
                }
            ]
            games = roms.get_games(config)
            self.assertEqual(len(games), 1)
            self.assertTrue(callable(games[0].launch))


if __name__ == "__main__":
    unittest.main()
