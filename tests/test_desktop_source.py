import unittest

from kabin.sources import desktop


class TestDesktopSource(unittest.TestCase):
    def test_excludes_steam_and_self(self):
        self.assertIn("steam.desktop", desktop._EXCLUDED_IDS)
        self.assertIn("kabin.desktop", desktop._EXCLUDED_IDS)
        self.assertIn("omagames.desktop", desktop._EXCLUDED_IDS)

    def test_excludes_emulator_frontends_from_game_library(self):
        self.assertIn("io.mgba.mGBA.desktop", desktop._EXCLUDED_IDS)
        self.assertIn("net.pcsx2.PCSX2.desktop", desktop._EXCLUDED_IDS)
        self.assertIn("org.ppsspp.PPSSPP.desktop", desktop._EXCLUDED_IDS)
        self.assertIn("dolphin-emu.desktop", desktop._EXCLUDED_IDS)
        self.assertIn("mame.desktop", desktop._EXCLUDED_IDS)
        self.assertIn("com.libretro.RetroArch.desktop", desktop._EXCLUDED_IDS)

    def test_rungame_regex_extracts_appid(self):
        match = desktop._STEAM_RUNGAME_RE.search("steam steam://rungameid/553850")
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "553850")

    def test_rungame_regex_no_match_for_other_exec(self):
        self.assertIsNone(desktop._STEAM_RUNGAME_RE.search("emulator --game /rom.sfc"))


if __name__ == "__main__":
    unittest.main()
