import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kabin.config import Config
from kabin.sources import discover_all_with_status


class TestDiscoverAllWithStatus(unittest.TestCase):
    def test_one_source_raising_does_not_block_the_others(self):
        # Regression: discover_all_with_status() used to call each source
        # scanner with no exception handling at all, so one misbehaving
        # source (an unreadable Steam library, a malformed reply from a
        # paired host, a file that vanished mid-scan) took every other
        # source's titles down with it for that refresh.
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "books"
            library.mkdir()
            (library / "A Book.epub").write_bytes(b"epub")
            config = Config(path=Path(tmp) / "config.json")
            config.media_dirs.append({"path": str(library), "media_type": "book"})
            # Isolate from this machine's real installed apps/Steam library
            # so only the book we just added, and the induced failure,
            # affect the result.
            config.sources["desktop"] = False
            config.sources["roms"] = False
            config.sources["remote"] = False

            with patch("kabin.sources.steam.get_games", side_effect=RuntimeError("boom")):
                games, _host_statuses = discover_all_with_status(config)

        self.assertEqual([g.title for g in games], ["A Book"])


if __name__ == "__main__":
    unittest.main()
