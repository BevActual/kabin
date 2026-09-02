import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kabin.config import Config
from kabin.sources import (
    discover_all_with_status,
    discover_local,
    discover_local_with_errors,
    discover_remote,
    remote_host_names,
)


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
                _games, errors = discover_local_with_errors(config)

        self.assertEqual([g.title for g in games], ["A Book"])
        # ...and the window gets told which source failed, instead of a
        # section quietly going empty.
        self.assertEqual(errors, {"Steam": "RuntimeError: boom"})

    def test_local_and_remote_are_separate_phases(self):
        # The window shows discover_local() as soon as it lands and merges
        # discover_remote() afterwards, so a powered-off paired host (a
        # full connect timeout) never delays this device's own titles.
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "books"
            library.mkdir()
            (library / "A Book.epub").write_bytes(b"epub")
            config = Config(path=Path(tmp) / "config.json")
            config.media_dirs.append({"path": str(library), "media_type": "book"})
            config.sources["steam"] = False
            config.sources["desktop"] = False
            config.sources["roms"] = False
            config.network["remote_hosts"] = [{"name": "Den", "token": "t"}]

            with patch(
                "kabin.sources.remote.fetch_remote_library",
                side_effect=AssertionError("local phase must not touch the network"),
            ):
                local = discover_local(config)
            self.assertEqual([g.title for g in local], ["A Book"])
            self.assertEqual(remote_host_names(config), ["Den"])

            with patch(
                "kabin.sources.remote.fetch_remote_library",
                return_value={"items": [{"id": "steam:1", "title": "Remote Game"}]},
            ):
                remote_games, statuses = discover_remote(config)
            self.assertEqual([g.title for g in remote_games], ["Remote Game"])
            self.assertEqual(statuses["Den"]["state"], "online")

            config.sources["remote"] = False
            self.assertEqual(remote_host_names(config), [])
            self.assertEqual(discover_remote(config), ([], {}))


if __name__ == "__main__":
    unittest.main()
