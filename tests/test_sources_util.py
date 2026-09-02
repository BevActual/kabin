import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kabin.sources._util import safe_mtime


class TestSafeMtime(unittest.TestCase):
    def test_returns_real_mtime_for_an_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.txt"
            path.write_bytes(b"x")
            self.assertEqual(safe_mtime(path), path.stat().st_mtime)

    def test_missing_file_returns_the_default_instead_of_raising(self):
        path = Path("/nonexistent/does-not-exist.txt")
        self.assertEqual(safe_mtime(path), 0.0)
        self.assertEqual(safe_mtime(path, default=-1.0), -1.0)

    def test_file_vanishing_between_listing_and_stat_does_not_raise(self):
        # The real-world trigger: a directory walk lists a file, then it's
        # deleted (a Syncthing-synced folder mid-sync, a flaky removable
        # drive, the user deleting it in a file manager) before stat()
        # runs on it a moment later.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.txt"
            path.write_bytes(b"x")
            with patch.object(Path, "stat", side_effect=OSError("vanished")):
                self.assertEqual(safe_mtime(path), 0.0)


if __name__ == "__main__":
    unittest.main()
