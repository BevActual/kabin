from __future__ import annotations

import gi
import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

Gst.init(None)


def plugin_available(name: str) -> bool:
    return Gst.ElementFactory.find(name) is not None


def native_helper_path() -> Path | None:
    project_helper = Path(__file__).resolve().parent.parent / "build" / "kabin-media-helper"
    if project_helper.is_file() and project_helper.stat().st_mode & 0o111:
        return project_helper
    installed = shutil.which("kabin-media-helper")
    return Path(installed) if installed else None


def _helper_fingerprint() -> tuple | None:
    """Identity of the helper binary right now, or None if there isn't one."""
    helper = native_helper_path()
    if helper is None:
        return None
    try:
        info = helper.stat()
    except OSError:
        return None
    return (str(helper), info.st_mtime_ns, info.st_size)


@lru_cache(maxsize=4)
def _native_helper_status(fingerprint: tuple | None) -> dict:
    if fingerprint is None:
        return {"available": False, "validated": False, "error": "helper is not built"}
    try:
        result = subprocess.run(
            [fingerprint[0], "--self-test"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        payload = json.loads(result.stdout) if result.stdout else {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return {"available": True, "validated": False, "error": str(exc)}
    return {
        "available": True,
        "validated": result.returncode == 0 and payload.get("ok") is True,
        "error": result.stderr.strip() if result.returncode else "",
    }


def native_helper_status() -> dict:
    """Self-test result for the media helper, cached per binary.

    The self-test spawns the helper with a 10s timeout, so this can't run
    on every call (/v1/info hits it per request). Keying the cache on the
    binary's path+mtime+size instead of caching one result forever means
    building the helper mid-session - the documented workflow, since it's
    a separate build step - is picked up straight away, rather than
    Settings and /v1/info reporting "not built" until restart.
    """
    return _native_helper_status(_helper_fingerprint())


def media_capabilities() -> dict:
    helper = native_helper_status()
    encoders = []
    if plugin_available("nvh264enc"):
        encoders.append({"codec": "h264", "encoder": "nvh264enc", "hardware": True})
    if plugin_available("vah264enc"):
        encoders.append({"codec": "h264", "encoder": "vah264enc", "hardware": True})
    if plugin_available("openh264enc"):
        encoders.append({"codec": "h264", "encoder": "openh264enc", "hardware": False})
    if plugin_available("vp8enc"):
        encoders.append({"codec": "vp8", "encoder": "vp8enc", "hardware": False})

    captures = []
    if plugin_available("pipewiresrc"):
        captures.append("pipewire")
    if plugin_available("ximagesrc"):
        captures.append("x11")

    webrtc = plugin_available("webrtcbin")
    ready = helper["validated"] and webrtc and bool(encoders)
    return {
        "webrtc": webrtc,
        "captures": captures,
        "encoders": encoders,
        "audio": plugin_available("pipewiresrc") and plugin_available("opusenc"),
        "native_helper": helper,
        "backend": "kabin" if ready else "none",
        "ready": ready,
    }


def stream_offer(config=None) -> dict:
    """Kabin-owned media offer. No external Moonlight or Sunshine process."""
    del config
    helper = native_helper_status()
    if helper["validated"]:
        return {
            "status": "awaiting-negotiation",
            "protocol": "kabin",
            "transport": "webrtc",
        }
    return {
        "status": "unavailable",
        "protocol": "kabin",
        "transport": "webrtc",
        "error": helper.get("error") or "Kabin media helper is not ready",
    }


def test_pipeline_description() -> str:
    """A safe stream used to validate WebRTC before launching or capturing a game."""
    capabilities = media_capabilities()
    if not capabilities["webrtc"]:
        raise RuntimeError("GStreamer WebRTC support is not installed")
    if not plugin_available("vp8enc"):
        raise RuntimeError("No supported validation encoder is installed")
    return (
        "webrtcbin name=webrtc bundle-policy=max-bundle "
        "videotestsrc is-live=true pattern=ball ! "
        "video/x-raw,width=1280,height=720,framerate=60/1 ! "
        "videoconvert ! queue ! vp8enc deadline=1 cpu-used=8 keyframe-max-dist=60 ! "
        "rtpvp8pay pt=96 picture-id-mode=15-bit ! "
        "application/x-rtp,media=video,encoding-name=VP8,payload=96 ! webrtc."
    )
