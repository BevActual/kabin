import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kabin.streaming import (
    media_capabilities,
    native_helper_status,
    stream_offer,
    test_pipeline_description,
)


class TestStreamingCapabilities(unittest.TestCase):
    def test_detects_native_media_stack(self):
        available = {"webrtcbin", "pipewiresrc", "nvh264enc", "vp8enc", "opusenc"}
        with patch("kabin.streaming.plugin_available", side_effect=lambda name: name in available), patch(
            "kabin.streaming.native_helper_status",
            return_value={"available": True, "validated": True, "error": ""},
        ):
            capabilities = media_capabilities()
        self.assertTrue(capabilities["ready"])
        self.assertEqual(capabilities["backend"], "kabin")
        self.assertEqual(capabilities["captures"], ["pipewire"])
        self.assertTrue(any(item["hardware"] for item in capabilities["encoders"]))

    def test_external_apps_do_not_make_streaming_ready(self):
        with patch("kabin.streaming.plugin_available", return_value=False), patch(
            "kabin.streaming.native_helper_status",
            return_value={"available": False, "validated": False, "error": "helper is not built"},
        ):
            capabilities = media_capabilities()
        self.assertFalse(capabilities["ready"])
        self.assertEqual(capabilities["backend"], "none")

    def test_stream_offer_uses_kabin_protocol(self):
        with patch(
            "kabin.streaming.native_helper_status",
            return_value={"available": True, "validated": True, "error": ""},
        ):
            offer = stream_offer()
        self.assertEqual(offer["protocol"], "kabin")
        self.assertEqual(offer["transport"], "webrtc")
        self.assertEqual(offer["status"], "awaiting-negotiation")

    def test_validation_pipeline_never_captures_desktop(self):
        available = {"webrtcbin", "vp8enc"}
        with patch("kabin.streaming.plugin_available", side_effect=lambda name: name in available):
            pipeline = test_pipeline_description()
        self.assertIn("videotestsrc", pipeline)
        self.assertIn("webrtcbin", pipeline)
        self.assertNotIn("pipewiresrc", pipeline)

    def test_validation_pipeline_reports_missing_webrtc(self):
        with patch("kabin.streaming.plugin_available", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "WebRTC"):
                test_pipeline_description()


class TestNativeHelperStatusCache(unittest.TestCase):
    def test_building_the_helper_mid_session_is_noticed(self):
        # Regression: the status was cached forever, so after building the
        # helper (a documented separate step) Settings and /v1/info kept
        # reporting "helper is not built" until Kabin was restarted - and
        # the cache went stale the other way if it was deleted.
        with tempfile.TemporaryDirectory() as tmp:
            helper = Path(tmp) / "kabin-media-helper"

            def fake_path():
                return helper if helper.exists() else None

            self_test = '{"ok":true,"transport":"webrtc","codec":"vp8"}'
            with patch("kabin.streaming.native_helper_path", side_effect=fake_path), patch(
                "kabin.streaming.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=self_test, stderr=""),
            ):
                before = native_helper_status()
                self.assertFalse(before["available"])
                self.assertEqual(before["error"], "helper is not built")

                helper.write_text("#!/bin/sh\n")
                helper.chmod(0o755)

                after = native_helper_status()
                self.assertTrue(after["available"])
                self.assertTrue(after["validated"])

                helper.unlink()
                self.assertFalse(native_helper_status()["available"])


if __name__ == "__main__":
    unittest.main()
