import unittest

from kabin.settings import custom_emulator_command_error


class TestCustomEmulatorCommandError(unittest.TestCase):
    def test_valid_command_has_no_error(self):
        self.assertIsNone(custom_emulator_command_error("mycore {rom} --fullscreen"))

    def test_missing_rom_placeholder_is_rejected(self):
        self.assertIsNotNone(custom_emulator_command_error("mycore --fullscreen"))

    def test_unbalanced_quoting_is_rejected(self):
        # Regression: previously only the "{rom}" substring was checked
        # here, so a command shlex can't actually parse (e.g. an
        # unclosed quote) saved fine and only failed the next time that
        # ROM was launched, far from where the mistake was made.
        self.assertIsNotNone(custom_emulator_command_error('mycore "{rom}'))

    def test_quoted_rom_placeholder_is_fine(self):
        self.assertIsNone(custom_emulator_command_error('mycore "{rom}"'))


if __name__ == "__main__":
    unittest.main()
