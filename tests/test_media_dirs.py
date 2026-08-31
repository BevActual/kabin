import tempfile
import unittest
from pathlib import Path

from kabin.sources.media_dirs import get_items


class TestMediaDirs(unittest.TestCase):
    def test_scans_books_and_skips_other_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "The Hobbit.epub").write_bytes(b"epub")
            (root / "ignored.mp3").write_bytes(b"audio")
            items = get_items([{"path": tmp, "media_type": "book"}])
        self.assertEqual([item.title for item in items], ["The Hobbit"])
        self.assertEqual(items[0].media_type, "book")
        self.assertEqual(items[0].media_format, "epub")
        self.assertEqual(items[0].source, "book")
        self.assertTrue(items[0].extra.get("needs_artwork"))

    def test_groups_music_by_album_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp) / "Kind of Blue"
            album.mkdir()
            (album / "01 So What.flac").write_bytes(b"a")
            (album / "02 Freddie.flac").write_bytes(b"b")
            (album / "cover.jpg").write_bytes(b"jpg")
            (Path(tmp) / "loose.mp3").write_bytes(b"c")
            items = get_items([{"path": tmp, "media_type": "music"}])
        titles = {item.title for item in items}
        self.assertEqual(titles, {"Kind of Blue", "loose"})
        album_item = next(item for item in items if item.title == "Kind of Blue")
        self.assertEqual(album_item.media_format, "album")
        self.assertEqual(album_item.extra["track_count"], 2)
        self.assertTrue(album_item.icon_path.endswith("cover.jpg"))

    def test_cleans_archive_names_and_album_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            books = Path(tmp) / "books"
            comics = Path(tmp) / "comics"
            music = Path(tmp) / "music"
            books.mkdir()
            comics.mkdir()
            album = music / "King Gizzard - Sketches Of Brunswick East"
            album.mkdir(parents=True)
            (
                books / "Harry Potter and the Chamber of Secrets -- J_ K_ Rowling -- 1999.epub"
            ).write_bytes(b"epub")
            (
                comics / "Naruto,Vol_1 Naruto Uzumaki(Colored) -- Kishimoto Masashi -- Jump Comics.epub"
            ).write_bytes(b"epub")
            (album / "King Gizzard - Sketches Of Brunswick East - 01 Intro.mp3").write_bytes(b"a")
            items = get_items(
                [
                    {"path": str(books), "media_type": "book"},
                    {"path": str(comics), "media_type": "comic"},
                    {"path": str(music), "media_type": "music"},
                ]
            )
        by_type = {item.media_type: item for item in items}
        self.assertEqual(by_type["book"].title, "Harry Potter and the Chamber of Secrets")
        self.assertEqual(by_type["book"].creators, ["J.K. Rowling"])
        self.assertEqual(by_type["comic"].title, "Naruto Uzumaki")
        self.assertEqual(by_type["comic"].creators, ["Kishimoto Masashi"])
        self.assertEqual(by_type["comic"].series, "Naruto")
        self.assertEqual(by_type["comic"].series_index, 1)
        self.assertEqual(by_type["music"].title, "Sketches Of Brunswick East")
        self.assertEqual(by_type["music"].creators, ["King Gizzard"])

    def test_respects_enabled_kinds_and_hidden_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "Movie.mkv").write_bytes(b"vid")
            items = get_items(
                [{"path": tmp, "media_type": "video"}],
                hidden_ids={"video:Movie.mkv"},
            )
            self.assertEqual(items, [])
            self.assertEqual(
                get_items([{"path": tmp, "media_type": "video"}], enabled_kinds={"book"}),
                [],
            )


if __name__ == "__main__":
    unittest.main()
