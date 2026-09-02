from __future__ import annotations

import json
import subprocess
import threading
from queue import Empty, Queue

from .streaming import native_helper_path


class MediaHelperError(RuntimeError):
    pass


class MediaHelperSession:
    """JSON-line session with kabin-media-helper (host capture or client playback)."""

    def __init__(self, role: str, helper=None):
        executable = helper or native_helper_path()
        if executable is None:
            raise MediaHelperError("Kabin media helper is not built")
        self.role = role
        self.process = subprocess.Popen(
            [str(executable), "--session", role],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._events: Queue[dict] = Queue()
        self._stderr_lines: list[str] = []
        self._start_reader_threads()

    def _start_reader_threads(self) -> None:
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        self._stderr_reader = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_reader.start()

    def _read(self):
        assert self.process.stdout is not None
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._events.put(json.loads(line))
            except json.JSONDecodeError:
                self._events.put({"type": "error", "sdp": line})

    def _drain_stderr(self) -> None:
        # Just reading stdout isn't enough: an OS pipe fills at ~64KB, and
        # once it does the helper blocks the next time it writes to
        # stderr - silently wedging the whole session. Keep a short tail
        # so a failure at least explains itself instead of a bare
        # "exited"/"timed out".
        if not self.process.stderr:
            return
        for line in self.process.stderr:
            line = line.rstrip()
            if line:
                self._stderr_lines.append(line)
                del self._stderr_lines[:-20]

    def _stderr_tail(self) -> str:
        if not self._stderr_lines:
            return ""
        return " · " + " | ".join(self._stderr_lines[-3:])

    def send(self, payload: dict) -> None:
        if not self.process.stdin:
            raise MediaHelperError("media helper stdin is closed")
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()

    def wait(self, message_type: str, timeout: float = 12) -> dict:
        deadline_chunks = max(1, int(timeout / 0.2))
        for _ in range(deadline_chunks):
            try:
                event = self._events.get(timeout=0.2)
            except Empty:
                if self.process.poll() is not None:
                    raise MediaHelperError(f"media helper exited{self._stderr_tail()}")
                continue
            if event.get("type") == "error":
                raise MediaHelperError(event.get("sdp") or "media helper error")
            if event.get("type") == message_type:
                return event
        raise MediaHelperError(f"timed out waiting for {message_type}{self._stderr_tail()}")

    def close(self) -> None:
        try:
            self.send({"type": "close"})
        except Exception:
            pass
        if self.process.stdin:
            try:
                self.process.stdin.close()
            except Exception:
                pass
        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass


def create_client_offer(session: MediaHelperSession) -> str:
    session.wait("hello")
    offer = session.wait("offer")
    sdp = offer.get("sdp")
    if not sdp:
        raise MediaHelperError("client helper produced no offer")
    return sdp


class PlaybackSession(MediaHelperSession):
    """Owned local or remote media playback through kabin-media-helper --play."""

    def __init__(self, uri: str, start: float = 0, authorization: str | None = None, helper=None):
        executable = helper or native_helper_path()
        if executable is None:
            raise MediaHelperError("Kabin media helper is not built")
        command = [str(executable), "--play", uri]
        if start:
            command.extend(["--start", f"{start:.3f}"])
        env = None
        if authorization:
            import os

            env = os.environ.copy()
            env["KABIN_MEDIA_AUTH"] = authorization
        self.role = "play"
        self.position = start or 0.0
        self.duration = 0.0
        self.paused = False
        self.ended = False
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        self._events: Queue[dict] = Queue()
        self._stderr_lines: list[str] = []
        self._start_reader_threads()

    def _read(self):
        assert self.process.stdout is not None
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                event = {"type": "error", "sdp": line}
            if event.get("type") == "position":
                parts = str(event.get("sdp") or "0 0").split()
                try:
                    self.position = float(parts[0])
                    if len(parts) > 1:
                        self.duration = float(parts[1])
                except ValueError:
                    pass
            if event.get("type") == "eos":
                self.ended = True
            self._events.put(event)

    def pause(self) -> None:
        self.send({"type": "pause"})
        self.paused = True

    def resume(self) -> None:
        self.send({"type": "resume"})
        self.paused = False

    def toggle_pause(self) -> None:
        if self.paused:
            self.resume()
        else:
            self.pause()

    def seek(self, seconds: float) -> None:
        position = max(0.0, float(seconds))
        self.send({"type": "seek", "sdp": f"{position:.3f}"})
        self.position = position

    def set_volume(self, volume: float) -> None:
        self.send({"type": "volume", "sdp": f"{max(0.0, min(1.0, float(volume))):.3f}"})


def answer_host_offer(session: MediaHelperSession, offer_sdp: str) -> str:
    session.wait("hello")
    session.send({"type": "offer", "sdp": offer_sdp})
    answer = session.wait("answer")
    sdp = answer.get("sdp")
    if not sdp:
        raise MediaHelperError("host helper produced no answer")
    return sdp
