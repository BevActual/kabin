import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kabin.sources import roms


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
                    "emulator": "echo {rom}",
                }
            ]
            games = roms.get_games(config)
            titles = sorted(g.title for g in games)
            self.assertEqual(titles, ["Chrono Trigger", "Super Metroid"])
            self.assertTrue(all(g.source == "roms" for g in games))
            self.assertTrue(all(g.subtitle == "SNES" for g in games))

    def test_existing_gba_library_inherits_zip_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "Pokemon.zip").touch()
            config = [{
                "path": str(base),
                "system": "gba",
                "extensions": ["gba"],
                "emulator": "mgba {rom}",
            }]
            games = roms.get_games(config)
            self.assertEqual([game.title for game in games], ["Pokemon"])

    def test_skips_entry_without_rom_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "game.sfc").write_bytes(b"")
            config = [
                {
                    "path": str(base),
                    "system": "SNES",
                    "extensions": ["sfc"],
                    "emulator": "emulator --game",
                }
            ]
            self.assertEqual(roms.get_games(config), [])

    def test_skips_missing_directory(self):
        config = [
            {
                "path": "/nonexistent/roms",
                "system": "SNES",
                "extensions": ["sfc"],
                "emulator": "echo {rom}",
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
                    "emulator": "echo {rom}",
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

    def test_structured_emulator_profile_launches_without_shell_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            rom = Path(tmp) / "Game With Spaces.gba"
            rom.touch()
            config = [{
                "path": tmp,
                "system": "gba",
                "extensions": ["gba"],
                "emulator": {
                    "id": "mgba",
                    "runtime": "native",
                    "executable": "/usr/bin/mgba-qt",
                },
            }]
            game = roms.get_games(config)[0]
            with patch("kabin.sources.roms.subprocess.Popen") as popen:
                game.launch()
            popen.assert_called_once_with([
                "/usr/bin/mgba-qt",
                str(rom),
            ])


if __name__ == "__main__":
    unittest.main()
