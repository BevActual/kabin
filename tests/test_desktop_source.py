import unittest

from omagames.sources import desktop


class TestDesktopSource(unittest.TestCase):
    def test_excludes_steam_and_self(self):
        self.assertIn("steam.desktop", desktop._EXCLUDED_IDS)
        self.assertIn("omagames.desktop", desktop._EXCLUDED_IDS)

    def test_rungame_regex_extracts_appid(self):
        match = desktop._STEAM_RUNGAME_RE.search("steam steam://rungameid/553850")
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "553850")

    def test_rungame_regex_no_match_for_other_exec(self):
        self.assertIsNone(desktop._STEAM_RUNGAME_RE.search("retroarch -L core.so /rom.sfc"))


if __name__ == "__main__":
    unittest.main()
