import unittest
from unittest.mock import patch

from kabin.streaming import media_capabilities, stream_offer, test_pipeline_description


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


if __name__ == "__main__":
    unittest.main()
