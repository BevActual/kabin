import tempfile
import unittest
from pathlib import Path

from kabin.emulation import connected_controllers, settings_for_preset, system_readiness
from kabin.systems import get_system


class TestEmulationProfiles(unittest.TestCase):
    def test_quality_preset_enables_rewind(self):
        settings = settings_for_preset("quality")
        self.assertTrue(settings["rewind"])
        self.assertTrue(settings["vsync"])

    def test_unknown_preset_falls_back_to_balanced(self):
        self.assertEqual(settings_for_preset("missing")["preset"], "balanced")

    def test_discovers_linux_joystick_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp)
            (input_dir / "usb-Microsoft_Xbox_Controller-event-joystick").touch()
            self.assertEqual(
                connected_controllers(input_dir),
                ["Microsoft Xbox Controller"],
            )

    def test_readiness_reports_unconfigured_system(self):
        status = system_readiness(get_system("snes"), [])
        self.assertFalse(status["ready"])
        self.assertEqual(status["state"], "Not configured")

    def test_readiness_requires_firmware_for_playstation(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = {
                "system": "ps1",
                "path": tmp,
                "emulator": {"runtime": "flatpak", "executable": "org.duckstation.DuckStation"},
            }
            status = system_readiness(get_system("ps1"), [entry])
        self.assertFalse(status["ready"])
        self.assertEqual(status["state"], "BIOS is required")

    def test_readiness_accepts_complete_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "snes9x"
            executable.touch(mode=0o755)
            entry = {
                "system": "snes",
                "path": tmp,
                "emulator": {"executable": str(executable)},
            }
            status = system_readiness(get_system("snes"), [entry])
        self.assertTrue(status["ready"])

    def test_readiness_detects_stale_emulator_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = {
                "system": "snes",
                "path": tmp,
                "emulator": {"runtime": "native", "executable": "/missing/snes9x"},
            }
            status = system_readiness(get_system("snes"), [entry])
        self.assertFalse(status["ready"])
        self.assertEqual(status["state"], "Emulator needs repair")


if __name__ == "__main__":
    unittest.main()
