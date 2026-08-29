import json
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


class TestCleanDescription(unittest.TestCase):
    def test_strips_imgvid_blocks(self):
        text = '[imgvid poster.avif="x.avif" webm="x.webm"][/imgvid]\nHello world.'
        self.assertEqual(steam.clean_description(text), "Hello world.")

    def test_strips_bbcode_tags_keeping_inner_text(self):
        text = "[h2]URGENT BROADCAST[/h2]\n[b]Freedom.[/b] Peace."
        self.assertEqual(steam.clean_description(text), "URGENT BROADCAST\nFreedom. Peace.")

    def test_collapses_excess_blank_lines(self):
        text = "Line one.\n\n\n\n\nLine two."
        self.assertEqual(steam.clean_description(text), "Line one.\n\nLine two.")

    def test_empty_input(self):
        self.assertEqual(steam.clean_description(""), "")
        self.assertEqual(steam.clean_description(None), "")


class TestLoadLocalMetadata(unittest.TestCase):
    def _write_librarycache(self, steam_root: Path, user_id: str, appid: str, payload: list):
        cache_dir = steam_root / "userdata" / user_id / "config" / "librarycache"
        cache_dir.mkdir(parents=True)
        (cache_dir / f"{appid}.json").write_text(json.dumps(payload))

    def test_reads_description_and_credits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "steamapps").mkdir()
            payload = [
                ["descriptions", {"data": {"strFullDescription": "[b]Hello[/b] world."}}],
                [
                    "associations",
                    {
                        "data": {
                            "rgDevelopers": [{"strName": "Arrowhead Game Studios"}],
                            "rgPublishers": [{"strName": "PlayStation Publishing LLC"}],
                        }
                    },
                ],
            ]
            self._write_librarycache(root, "117092244", "553850", payload)

            metadata = steam.load_local_metadata("553850", str(root))
            self.assertEqual(metadata["description"], "Hello world.")
            self.assertEqual(metadata["developers"], ["Arrowhead Game Studios"])
            self.assertEqual(metadata["publishers"], ["PlayStation Publishing LLC"])

    def test_missing_cache_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "steamapps").mkdir()
            (root / "userdata" / "117092244" / "config" / "librarycache").mkdir(parents=True)

            self.assertEqual(steam.load_local_metadata("553850", str(root)), {})

    def test_missing_root_returns_empty(self):
        with unittest.mock.patch.object(steam, "_DEFAULT_ROOTS", [Path("/nonexistent/default")]):
            self.assertEqual(steam.load_local_metadata("553850", "/nonexistent/override"), {})


if __name__ == "__main__":
    unittest.main()
