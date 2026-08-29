import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kabin.managed import (
    ManagedRuntimeError,
    RUNTIME_BY_ID,
    install_runtime,
    installed_executable,
    recommended_runtime,
    resolve_asset,
)


class FakeResponse:
    def __init__(self, data):
        self._stream = io.BytesIO(data)

    def read(self, size=-1):
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def queued_opener(*responses):
    queue = list(responses)

    def open_response(_request, timeout=None):
        return FakeResponse(queue.pop(0))

    return open_response


class TestManagedRuntimes(unittest.TestCase):
    def test_recommends_duckstation_for_playstation(self):
        self.assertEqual(recommended_runtime("ps1").id, "duckstation")

    def test_does_not_recommend_unverified_mgba_appimage(self):
        self.assertIsNone(recommended_runtime("gba"))

    def test_refuses_release_without_digest(self):
        release = {
            "tag_name": "v1",
            "assets": [{
                "name": "DuckStation-x64.AppImage",
                "browser_download_url": "https://example.invalid/duckstation",
            }],
        }
        with patch("kabin.managed.architecture", return_value="x86_64"):
            with self.assertRaises(ManagedRuntimeError):
                resolve_asset(
                    RUNTIME_BY_ID["duckstation"],
                    queued_opener(json.dumps(release).encode()),
                )

    def test_installs_verified_runtime_atomically(self):
        payload = b"verified appimage"
        checksum = hashlib.sha256(payload).hexdigest()
        release = {
            "tag_name": "v1",
            "assets": [{
                "name": "DuckStation-x64.AppImage",
                "browser_download_url": "https://example.invalid/duckstation",
                "digest": f"sha256:{checksum}",
            }],
        }
        opener = queued_opener(json.dumps(release).encode(), payload)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("kabin.managed.architecture", return_value="x86_64"):
                executable = install_runtime(RUNTIME_BY_ID["duckstation"], root, opener)
            self.assertEqual(executable.read_bytes(), payload)
            self.assertTrue(executable.stat().st_mode & 0o100)
            self.assertEqual(installed_executable("duckstation", root), executable)
            self.assertFalse((executable.parent / ".duckstation.download").exists())

    def test_checksum_mismatch_does_not_install(self):
        release = {
            "tag_name": "v1",
            "assets": [{
                "name": "DuckStation-x64.AppImage",
                "browser_download_url": "https://example.invalid/duckstation",
                "digest": f"sha256:{'0' * 64}",
            }],
        }
        opener = queued_opener(json.dumps(release).encode(), b"tampered")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("kabin.managed.architecture", return_value="x86_64"):
                with self.assertRaises(ManagedRuntimeError):
                    install_runtime(RUNTIME_BY_ID["duckstation"], root, opener)
            self.assertIsNone(installed_executable("duckstation", root))


if __name__ == "__main__":
    unittest.main()
