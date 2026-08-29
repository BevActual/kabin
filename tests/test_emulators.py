import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kabin.emulators import EmulatorChoice, build_command, detect_emulators, launch_environment
from kabin.systems import get_system


class TestEmulators(unittest.TestCase):
    def test_choice_serializes_to_config(self):
        choice = EmulatorChoice("mgba", "mGBA", "native", "/usr/bin/mgba-qt")
        self.assertEqual(choice.to_config()["id"], "mgba")

    def test_builds_native_command_as_arguments(self):
        profile = {"id": "mgba", "runtime": "native", "executable": "/usr/bin/mgba-qt"}
        rom = Path("/games/Game With Spaces.gba")
        self.assertEqual(build_command(profile, rom), ["/usr/bin/mgba-qt", str(rom)])

    def test_builds_mame_command_with_rom_directory_and_driver_name(self):
        profile = {"id": "mame", "runtime": "native", "executable": "/usr/bin/mame"}
        rom = Path("/games/arcade/pacman.zip")
        self.assertEqual(
            build_command(profile, rom),
            ["/usr/bin/mame", "-rompath", "/games/arcade", "pacman"],
        )

    def test_builds_managed_command_without_flatpak_wrapper(self):
        profile = {
            "id": "mgba",
            "runtime": "managed",
            "executable": "/data/kabin/emulators/mgba/mgba",
        }
        rom = Path("/games/test.gba")
        self.assertEqual(build_command(profile, rom), [profile["executable"], str(rom)])

    def test_managed_environment_is_isolated_beside_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "duckstation" / "duckstation"
            profile = {"runtime": "managed", "executable": str(executable)}
            environment = launch_environment(profile)
            self.assertEqual(
                environment["XDG_CONFIG_HOME"],
                str(executable.parent / "profile/config"),
            )
            self.assertTrue((executable.parent / "profile/data").is_dir())

    def test_native_environment_is_not_overridden(self):
        self.assertIsNone(launch_environment({"runtime": "native"}))

    def test_builds_flatpak_dolphin_command(self):
        profile = {
            "id": "dolphin",
            "runtime": "flatpak",
            "executable": "org.DolphinEmu.dolphin-emu",
        }
        command = build_command(profile, Path("/games/Mario.rvz"))
        self.assertEqual(command[:5], ["flatpak", "run", "org.DolphinEmu.dolphin-emu", "--batch", "--exec"])

    def test_shared_fullscreen_setting_is_applied_per_emulator(self):
        profile = {"id": "snes9x", "runtime": "native", "executable": "/usr/bin/snes9x"}
        command = build_command(profile, Path("/games/test.sfc"), {"fullscreen": True})
        self.assertEqual(command, ["/usr/bin/snes9x", "-fullscreen", "/games/test.sfc"])

    def test_detects_native_mgba(self):
        def which(executable):
            return "/usr/bin/mgba-qt" if executable == "mgba-qt" else None

        with patch("kabin.emulators.shutil.which", side_effect=which):
            choices = detect_emulators(get_system("gba"))
        self.assertEqual([(choice.id, choice.name) for choice in choices], [("mgba", "mGBA")])

    def test_detects_user_flatpak_pcsx2(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".local/share/flatpak/app/net.pcsx2.PCSX2").mkdir(parents=True)
            with patch("kabin.emulators.shutil.which", return_value=None), patch(
                "kabin.emulators.installed_executable", return_value=None
            ):
                choices = detect_emulators(get_system("ps2"), home=home)
        self.assertEqual(choices[0].id, "pcsx2")
        self.assertEqual(choices[0].runtime, "flatpak")

    def test_does_not_offer_uninstalled_emulator(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("kabin.emulators.shutil.which", return_value=None), patch(
                "kabin.emulators.installed_executable", return_value=None
            ):
                self.assertEqual(detect_emulators(get_system("gba"), home=Path(tmp)), [])


if __name__ == "__main__":
    unittest.main()
