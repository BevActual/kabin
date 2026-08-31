import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kabin.artwork import (
    apply_chosen_covers,
    cached_cover,
    clean_game_title,
    extract_epub_cover,
    fetch_openlibrary_cover,
    fetch_steamgriddb_cover,
    fetch_remote_cover,
    folder_cover,
    install_cover_from_url,
    local_cover,
    resolve_cover,
    save_chosen_cover,
    search_cover_candidates,
    search_openlibrary_candidates,
    search_steamgriddb_candidates,
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
        self.assertEqual(
            clean_game_title("Legend of Zelda, The - Majora's Mask (USA).z64"),
            "The Legend of Zelda - Majora's Mask",
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

    def test_fetches_openlibrary_cover_by_title_and_author(self):
        jpeg = b"\xff\xd8\xff" + b"\x00" * 3000
        responses = [
            json.dumps(
                {
                    "docs": [
                        {
                            "title": "Harry Potter and the Chamber of Secrets",
                            "author_name": ["J. K. Rowling"],
                            "cover_i": 8406786,
                        }
                    ]
                }
            ).encode(),
            jpeg,
        ]
        requests = []

        def opener(request, timeout=None):
            requests.append(request)
            return FakeResponse(responses.pop(0))

        with tempfile.TemporaryDirectory() as tmp:
            cover = fetch_openlibrary_cover(
                "Harry Potter and the Chamber of Secrets",
                "J.K. Rowling",
                "book:chamber.epub",
                Path(tmp),
                opener,
            )
            self.assertTrue(cover.is_file())
            self.assertEqual(cover.read_bytes(), jpeg)
            self.assertEqual(
                fetch_openlibrary_cover(
                    "Harry Potter and the Chamber of Secrets",
                    "J.K. Rowling",
                    "book:chamber.epub",
                    Path(tmp),
                    opener,
                ),
                cover,
            )
        self.assertEqual(len(requests), 2)
        self.assertIn("openlibrary.org/search.json", requests[0].full_url)
        self.assertIn("title=Harry", requests[0].full_url)
        self.assertIn("author=J.K.", requests[0].full_url)
        self.assertIn("covers.openlibrary.org/b/id/8406786-L.jpg", requests[1].full_url)
        self.assertEqual(requests[0].get_header("User-agent"), "Kabin/0.1")
        self.assertIsNone(requests[0].get_header("Authorization"))

    def test_openlibrary_skips_results_without_a_cover(self):
        def opener(_request, timeout=None):
            return FakeResponse(json.dumps({"docs": [{"title": "Unknown", "cover_i": None}]}).encode())

        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(
                fetch_openlibrary_cover("Unknown", "", "book:unknown.epub", Path(tmp), opener)
            )

    def test_extracts_cover_from_epub(self):
        import zipfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            epub = root / "book.epub"
            cache = root / "covers"
            with zipfile.ZipFile(epub, "w") as archive:
                archive.writestr(
                    "META-INF/container.xml",
                    """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
                )
                archive.writestr(
                    "OEBPS/content.opf",
                    """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="id" version="3.0">
  <metadata>
    <meta name="cover" content="cover"/>
  </metadata>
  <manifest>
    <item id="cover" href="cover.jpg" media-type="image/jpeg"/>
  </manifest>
  <spine></spine>
</package>""",
                )
                archive.writestr("OEBPS/cover.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 32)
            cover = extract_epub_cover(epub, cache)
            self.assertIsNotNone(cover)
            self.assertTrue(cover.is_file())
            self.assertEqual(cover.read_bytes()[:3], b"\xff\xd8\xff")
            self.assertEqual(extract_epub_cover(epub, cache), cover)

    def test_lists_steamgriddb_cover_choices(self):
        responses = [
            json.dumps({"data": [{"id": 42, "name": "Majora's Mask"}]}).encode(),
            json.dumps(
                {
                    "data": [
                        {
                            "url": "https://cdn.example/a.png",
                            "thumb": "https://cdn.example/a-t.png",
                            "style": "official",
                        },
                        {
                            "url": "https://cdn.example/b.png",
                            "thumb": "https://cdn.example/b-t.png",
                            "style": "alternate",
                        },
                    ]
                }
            ).encode(),
        ]

        def opener(_request, timeout=None):
            return FakeResponse(responses.pop(0))

        choices = search_steamgriddb_candidates("Majora's Mask", "key", opener)
        self.assertEqual(len(choices), 2)
        self.assertEqual(choices[1].caption, "Majora's Mask · alternate")
        self.assertEqual(choices[0].source, "steamgriddb")

    def test_lists_openlibrary_cover_choices(self):
        def opener(_request, timeout=None):
            return FakeResponse(
                json.dumps(
                    {
                        "docs": [
                            {
                                "title": "Chamber of Secrets",
                                "author_name": ["J. K. Rowling"],
                                "cover_i": 111,
                            },
                            {
                                "title": "Chamber of Secrets",
                                "author_name": ["J.K. Rowling"],
                                "cover_i": 222,
                            },
                        ]
                    }
                ).encode()
            )

        choices = search_openlibrary_candidates("Chamber of Secrets", "J.K. Rowling", opener)
        self.assertEqual([choice.image_url for choice in choices], [
            "https://covers.openlibrary.org/b/id/111-L.jpg",
            "https://covers.openlibrary.org/b/id/222-L.jpg",
        ])

    def test_routes_cover_search_by_kind(self):
        with patch("kabin.artwork.search_openlibrary_candidates", return_value=[]) as books:
            search_cover_candidates("Naruto", "comic", creator="Kishimoto")
            books.assert_called_once()
        with patch("kabin.artwork.search_coverartarchive_candidates", return_value=[]) as music:
            search_cover_candidates("Balkan Railway", "music", creator="Various Artists")
            music.assert_called_once()
        with patch("kabin.artwork.search_steamgriddb_candidates", return_value=[]) as games:
            search_cover_candidates("Mario Kart 64", "game", api_key="key")
            games.assert_called_once()

    def test_saves_and_applies_a_chosen_cover(self):
        from kabin.models import LibraryItem

        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        with tempfile.TemporaryDirectory() as tmp:
            cover = save_chosen_cover("book:chamber.epub", png, Path(tmp))
            self.assertTrue(cover.is_file())
            item = LibraryItem(id="book:chamber.epub", title="Chamber", source="book")
            apply_chosen_covers([item], {item.id: str(cover)})
            self.assertEqual(item.icon_path, str(cover))
            self.assertFalse(item.extra.get("needs_artwork"))

    def test_installs_chosen_cover_from_https(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

        def opener(_request, timeout=None):
            return FakeResponse(png)

        with tempfile.TemporaryDirectory() as tmp:
            cover = install_cover_from_url(
                "roms:n64:zelda.z64",
                "https://cdn.example/cover.png",
                Path(tmp),
                opener,
            )
            self.assertEqual(cover.read_bytes(), png)


if __name__ == "__main__":
    unittest.main()

