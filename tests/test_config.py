import tempfile
import unittest
from pathlib import Path

from omagames.config import Config


class TestConfig(unittest.TestCase):
    def test_defaults_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            self.assertEqual(config.rom_dirs, [])
            self.assertEqual(config.hidden, [])
            self.assertTrue(config.sources["steam"])

    def test_round_trips_rom_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(path=path)
            config.add_rom_dir("/roms/snes", "SNES", ["sfc"], "retroarch {rom}")

            reloaded = Config(path=path)
            self.assertEqual(len(reloaded.rom_dirs), 1)
            self.assertEqual(reloaded.rom_dirs[0]["system"], "SNES")

    def test_remove_rom_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(path=path)
            config.add_rom_dir("/roms/snes", "SNES", ["sfc"], "retroarch {rom}")
            config.add_rom_dir("/roms/gba", "GBA", ["gba"], "mgba {rom}")
            config.remove_rom_dir(0)
            self.assertEqual(len(config.rom_dirs), 1)
            self.assertEqual(config.rom_dirs[0]["system"], "GBA")

    def test_hide_and_unhide(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            config.hide("steam:553850")
            self.assertTrue(config.is_hidden("steam:553850"))
            config.unhide("steam:553850")
            self.assertFalse(config.is_hidden("steam:553850"))

    def test_ignores_corrupt_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("not json")
            config = Config(path=path)
            self.assertEqual(config.rom_dirs, [])


if __name__ == "__main__":
    unittest.main()
