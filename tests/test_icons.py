import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from kabin import icons

_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "3de70000000c4944415478da62660100000600037e"
)


class TestSupportedImage(unittest.TestCase):
    def test_accepts_png_jpeg_and_webp_magic_bytes(self):
        self.assertTrue(icons._supported_image(_PNG_BYTES))
        self.assertTrue(icons._supported_image(b"\xff\xd8\xff\xe0rest of a jpeg"))
        self.assertTrue(icons._supported_image(b"RIFF\x00\x00\x00\x00WEBPVP8 "))

    def test_rejects_unrecognized_or_empty_data(self):
        self.assertFalse(icons._supported_image(b""))
        self.assertFalse(icons._supported_image(b"<html>not an image</html>"))
        self.assertFalse(icons._supported_image(b"RIFF\x00\x00\x00\x00AVI garbage"))


class _IconsCacheRootTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self._original_cache_root = icons._CACHE_ROOT
        self._original_legacy_root = icons._LEGACY_CACHE_ROOT
        icons._CACHE_ROOT = root / "kabin" / "steam"
        icons._LEGACY_CACHE_ROOT = root / "omagames" / "steam"
        self.addCleanup(self._restore_roots)

    def _restore_roots(self):
        icons._CACHE_ROOT = self._original_cache_root
        icons._LEGACY_CACHE_ROOT = self._original_legacy_root


class TestCachedPath(_IconsCacheRootTestCase):
    def test_missing_returns_none(self):
        self.assertIsNone(icons.cached_path("620"))

    def test_prefers_current_cache_over_legacy(self):
        current = icons._CACHE_ROOT / "cover" / "620.jpg"
        current.parent.mkdir(parents=True)
        current.write_bytes(b"art")
        self.assertEqual(icons.cached_path("620"), current)

    def test_falls_back_to_legacy_cache(self):
        legacy = icons._LEGACY_CACHE_ROOT / "cover" / "620.jpg"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"art")
        self.assertEqual(icons.cached_path("620"), legacy)

    def test_logo_kind_uses_its_own_extension(self):
        logo = icons._CACHE_ROOT / "logo" / "620.png"
        logo.parent.mkdir(parents=True)
        logo.write_bytes(b"art")
        self.assertEqual(icons.cached_path("620", kind="logo"), logo)
        self.assertIsNone(icons.cached_path("620"))


@contextmanager
def _fake_response(data: bytes):
    yield SimpleNamespace(read=lambda _n: data)


class TestDownload(_IconsCacheRootTestCase):
    def test_writes_first_working_url_and_returns_its_path(self):
        with patch("kabin.icons.urllib.request.urlopen", return_value=_fake_response(_PNG_BYTES)):
            path = icons._download("620", "cover")
        self.assertEqual(path, icons._CACHE_ROOT / "cover" / "620.jpg")
        self.assertEqual(path.read_bytes(), _PNG_BYTES)

    def test_skips_urls_that_fail_and_tries_the_next_one(self):
        calls = []

        def fake_urlopen(request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise OSError("first host down")
            return _fake_response(_PNG_BYTES)

        with patch("kabin.icons.urllib.request.urlopen", side_effect=fake_urlopen):
            path = icons._download("620", "cover")
        self.assertEqual(len(calls), 2)
        self.assertEqual(path, icons._CACHE_ROOT / "cover" / "620.jpg")

    def test_rejects_non_image_response_and_returns_none(self):
        with patch(
            "kabin.icons.urllib.request.urlopen",
            side_effect=lambda *_a, **_kw: _fake_response(b"<html>404</html>"),
        ):
            path = icons._download("620", "cover")
        self.assertIsNone(path)
        self.assertFalse((icons._CACHE_ROOT / "cover" / "620.jpg").exists())

    def test_all_urls_failing_returns_none(self):
        with patch("kabin.icons.urllib.request.urlopen", side_effect=OSError("offline")):
            path = icons._download("620", "cover")
        self.assertIsNone(path)


if __name__ == "__main__":
    unittest.main()
