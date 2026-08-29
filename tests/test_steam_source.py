import tempfile
import unittest
import unittest.mock
from pathlib import Path

from omagames.sources import steam


class TestParseVdf(unittest.TestCase):
    def test_parses_nested_appmanifest(self):
        text = """
        "AppState"
        {
            "appid"     "553850"
            "name"      "HELLDIVERS\\u2122 2"
            "InstalledDepots"
            {
                "553851" { "manifest" "1" }
            }
        }
        """
        data = steam.parse_vdf(text)
        self.assertEqual(data["AppState"]["appid"], "553850")
        self.assertIn("InstalledDepots", data["AppState"])

    def test_parses_libraryfolders(self):
        text = """
        "libraryfolders"
        {
            "0"
            {
                "path" "/home/andrew/.local/share/Steam"
                "apps"
                {
                    "553850" "123"
                }
            }
        }
        """
        data = steam.parse_vdf(text)
        self.assertEqual(
            data["libraryfolders"]["0"]["path"], "/home/andrew/.local/share/Steam"
        )


class TestIsRealGame(unittest.TestCase):
    def test_filters_known_tools(self):
        for name in (
            "Steamworks Common Redistributables",
            "Proton Experimental",
            "Proton Hotfix",
            "Steam Linux Runtime 3.0 (sniper)",
            "Steam Linux Runtime 4.0",
        ):
            self.assertFalse(steam._is_real_game(name), name)

    def test_keeps_real_games(self):
        for name in ("HELLDIVERS 2", "Portal 2", "Proteus"):
            self.assertTrue(steam._is_real_game(name), name)

    def test_rejects_empty(self):
        self.assertFalse(steam._is_real_game(""))
        self.assertFalse(steam._is_real_game(None))


class TestGetGames(unittest.TestCase):
    def _write_manifest(self, steamapps_dir: Path, appid: str, name: str):
        (steamapps_dir / f"appmanifest_{appid}.acf").write_text(
            f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{name}"\n}}\n'
        )

    def test_scans_and_filters_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            steamapps = root / "steamapps"
            steamapps.mkdir()
            self._write_manifest(steamapps, "553850", "HELLDIVERS 2")
            self._write_manifest(steamapps, "228980", "Steamworks Common Redistributables")

            games = steam.get_games(str(root))
            self.assertEqual(len(games), 1)
            self.assertEqual(games[0].title, "HELLDIVERS 2")
            self.assertEqual(games[0].id, "steam:553850")
            self.assertEqual(games[0].extra["appid"], "553850")

    def test_respects_hidden_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            steamapps = root / "steamapps"
            steamapps.mkdir()
            self._write_manifest(steamapps, "553850", "HELLDIVERS 2")

            games = steam.get_games(str(root), hidden_ids={"steam:553850"})
            self.assertEqual(games, [])

    def test_missing_root_returns_empty(self):
        with unittest.mock.patch.object(steam, "_DEFAULT_ROOTS", [Path("/nonexistent/default")]):
            games = steam.get_games("/nonexistent/override")
        self.assertEqual(games, [])


if __name__ == "__main__":
    unittest.main()
