import io
import json
import tempfile
import unittest
from pathlib import Path

from kabin.artwork import (
    cached_cover,
    clean_game_title,
    fetch_steamgriddb_cover,
    fetch_remote_cover,
    folder_cover,
    local_cover,
    resolve_cover,
)


class FakeResponse:
    def __init__(self, data):
        self.stream = io.BytesIO(data)

    def read(self, size=-1):
        return self.stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class TestArtwork(unittest.TestCase):
    def test_cleans_common_rom_tags(self):
        self.assertEqual(
            clean_game_title("Pokemon - FireRed Version (USA) [Rev 1].zip"),
            "Pokemon - FireRed Version",
        )

    def test_finds_cover_beside_rom(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            rom = directory / "Game.gba"
            cover = directory / "Game.jpg"
            rom.touch()
            cover.touch()
            self.assertEqual(local_cover(rom), cover)

    def test_finds_cover_in_covers_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            rom = directory / "Game.zip"
            cover = directory / "covers/Game.png"
            cover.parent.mkdir()
            cover.touch()
            self.assertEqual(local_cover(rom), cover)

    def test_finds_folder_cover_for_albums(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            cover = directory / "folder.jpg"
            cover.touch()
            self.assertEqual(folder_cover(directory), cover)

    def test_cached_cover_uses_stable_game_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import hashlib

            game_id = "roms:gba:Game.zip"
            cover = root / f"{hashlib.sha256(game_id.encode()).hexdigest()}.webp"
            cover.touch()
            self.assertEqual(cached_cover(game_id, root), cover)

    def test_fetches_and_caches_portrait_cover_with_authorization(self):
        responses = [
            json.dumps({"data": [{"id": 42, "name": "Pokemon FireRed"}]}).encode(),
            json.dumps({"data": [{"width": 600, "height": 900, "url": "https://cdn.example/cover.png"}]}).encode(),
            b"\x89PNG\r\n\x1a\nimage-data",
        ]
        requests = []

        def opener(request, timeout=None):
            requests.append(request)
            return FakeResponse(responses.pop(0))

        with tempfile.TemporaryDirectory() as tmp:
            cover = fetch_steamgriddb_cover(
                "Pokemon FireRed",
                "roms:gba:Pokemon.zip",
                "api-secret",
                Path(tmp),
                opener,
            )
            self.assertTrue(cover.is_file())
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer api-secret")
        self.assertEqual(requests[1].get_header("Authorization"), "Bearer api-secret")
        self.assertIsNone(requests[2].get_header("Authorization"))

    def test_refuses_non_image_download(self):
        responses = [
            json.dumps({"data": [{"id": 42, "name": "Game"}]}).encode(),
            json.dumps({"data": [{"width": 600, "height": 900, "url": "https://cdn.example/cover"}]}).encode(),
            b"<html>not an image</html>",
        ]

        def opener(_request, timeout=None):
            return FakeResponse(responses.pop(0))

        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(
                fetch_steamgriddb_cover("Game", "roms:gba:Game.zip", "key", Path(tmp), opener)
            )

    def test_fetches_authenticated_remote_cover_into_separate_cache(self):
        requests = []

        def opener(request, timeout=None):
            requests.append(request)
            return FakeResponse(b"\x89PNG\r\n\x1a\nremote-image")

        host = {"name": "Gaming PC", "address": "10.0.0.2", "port": 42424}
        with tempfile.TemporaryDirectory() as tmp:
            cover = fetch_remote_cover(
                host, "device-token", "roms:gba:test.gba", Path(tmp), opener
            )
            self.assertTrue(cover.is_file())
            self.assertEqual(fetch_remote_cover(host, "device-token", "roms:gba:test.gba", Path(tmp), opener), cover)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer device-token")
        self.assertIn("id=roms%3Agba%3Atest.gba", requests[0].full_url)

    def test_resolve_cover_skips_network_when_fetch_disabled(self):
        from unittest.mock import patch

        with patch("kabin.artwork.fetch_steamgriddb_cover") as fetch:
            self.assertIsNone(
                resolve_cover(
                    "Game",
                    "roms:gba:Game.zip",
                    {"steamgriddb_api_key": "secret"},
                    fetch=False,
                )
            )
            fetch.assert_not_called()

    def test_resolve_cover_uses_cached_art_for_desktop_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            from unittest.mock import patch

            root = Path(tmp)
            game_id = "desktop:example.desktop"
            import hashlib

            cover = root / f"{hashlib.sha256(game_id.encode()).hexdigest()}.png"
            cover.touch()
            with patch("kabin.artwork.artwork_root", return_value=root):
                self.assertEqual(resolve_cover("Example", game_id, {}), cover)


if __name__ == "__main__":
    unittest.main()
