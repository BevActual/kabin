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
