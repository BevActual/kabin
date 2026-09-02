import tempfile
import unittest
from pathlib import Path

from kabin.systems import firmware_files, get_system


class TestSystems(unittest.TestCase):
    def test_playstation_requires_firmware(self):
        self.assertTrue(get_system("ps1").firmware_required)
        self.assertTrue(get_system("ps2").firmware_required)
        self.assertFalse(get_system("gba").firmware_required)

    def test_chip_label_uses_short_name(self):
        self.assertEqual(get_system("nes").chip_label, "NES")
        self.assertEqual(get_system("ps1").chip_label, "PS1")

    def test_firmware_scan_accepts_bin_and_rom_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "bios.bin").touch()
            (directory / "firmware.rom").touch()
            (directory / "notes.txt").touch()
            self.assertEqual(
                [path.name for path in firmware_files(directory)],
                ["bios.bin", "firmware.rom"],
            )

    def test_missing_firmware_directory_is_empty(self):
        self.assertEqual(firmware_files("/definitely/missing"), [])


if __name__ == "__main__":
    unittest.main()
