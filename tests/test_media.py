import subprocess
import unittest
from queue import Queue
from unittest.mock import patch

from kabin.media import (
    MediaHelperError,
    MediaHelperSession,
    PlaybackSession,
    answer_host_offer,
    create_client_offer,
)


class _QueueFile:
    def __init__(self, incoming: Queue):
        self._incoming = incoming

    def __iter__(self):
        while True:
            line = self._incoming.get()
            if line is None:
                return
            yield line


class _ScriptedStdin:
    def __init__(self, incoming: Queue, answers: dict[str, list[str]]):
        self._incoming = incoming
        self._answers = answers
        self.writes = []

    def write(self, text: str) -> int:
        self.writes.append(text)
        payload = text.strip()
        for needle, lines in self._answers.items():
            if needle in payload:
                for line in lines:
                    self._incoming.put(line)
        return len(text)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self._incoming.put(None)


class _ScriptedProcess:
    def __init__(self, hello_lines: list[str], answers: dict[str, list[str]]):
        self._incoming = Queue()
        for line in hello_lines:
            self._incoming.put(line)
        self.stdin = _ScriptedStdin(self._incoming, answers)
        self.stdout = _QueueFile(self._incoming)
        self.stderr = None
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 0
        self._incoming.put(None)

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def kill(self):
        self.returncode = -9


class TestMediaHelperSession(unittest.TestCase):
    def test_create_client_offer_reads_helper_sdp(self):
        process = _ScriptedProcess(
            [
                '{"type":"hello","sdp":"client"}\n',
                '{"type":"offer","sdp":"v=0 offer"}\n',
            ],
            {},
        )
        with patch("kabin.media.native_helper_path", return_value="/tmp/helper"), patch(
            "kabin.media.subprocess.Popen", return_value=process
        ):
            session = MediaHelperSession("client")
            self.assertEqual(create_client_offer(session), "v=0 offer")
            session.close()

    def test_answer_host_offer_sends_remote_sdp(self):
        process = _ScriptedProcess(
            ['{"type":"hello","sdp":"host"}\n'],
            {'"type": "offer"': ['{"type":"answer","sdp":"v=0 answer"}\n']},
        )
        with patch("kabin.media.native_helper_path", return_value="/tmp/helper"), patch(
            "kabin.media.subprocess.Popen", return_value=process
        ):
            session = MediaHelperSession("host")
            self.assertEqual(answer_host_offer(session, "v=0 offer"), "v=0 answer")
            session.close()

    def test_helper_error_is_raised(self):
        process = _ScriptedProcess(
            ['{"type":"hello","sdp":"client"}\n', '{"type":"error","sdp":"no encoder"}\n'],
            {},
        )
        with patch("kabin.media.native_helper_path", return_value="/tmp/helper"), patch(
            "kabin.media.subprocess.Popen", return_value=process
        ):
            session = MediaHelperSession("client")
            with self.assertRaisesRegex(MediaHelperError, "no encoder"):
                create_client_offer(session)
            session.close()

    def test_playback_session_tracks_position(self):
        process = _ScriptedProcess(
            [
                '{"type":"hello","sdp":"play"}\n',
                '{"type":"ready","sdp":"file:///film.mkv"}\n',
                '{"type":"position","sdp":"12.5 100.0"}\n',
            ],
            {},
        )
        with patch("kabin.media.native_helper_path", return_value="/tmp/helper"), patch(
            "kabin.media.subprocess.Popen", return_value=process
        ) as popped:
            session = PlaybackSession("file:///film.mkv", start=12.5, authorization="Bearer t")
            self.assertEqual(session.wait("ready")["sdp"], "file:///film.mkv")
            session.wait("position")
            self.assertEqual(session.position, 12.5)
            self.assertEqual(session.duration, 100.0)
            session.close()
        command = popped.call_args.args[0]
        self.assertEqual(command[:3], ["/tmp/helper", "--play", "file:///film.mkv"])
        self.assertEqual(command[3:5], ["--start", "12.500"])
        self.assertEqual(popped.call_args.kwargs["env"]["KABIN_MEDIA_AUTH"], "Bearer t")

    def test_playback_session_sends_transport_commands(self):
        process = _ScriptedProcess(
            ['{"type":"hello","sdp":"play"}\n', '{"type":"ready","sdp":"file:///a.mp3"}\n'],
            {},
        )
        with patch("kabin.media.native_helper_path", return_value="/tmp/helper"), patch(
            "kabin.media.subprocess.Popen", return_value=process
        ):
            session = PlaybackSession("file:///a.mp3")
            session.wait("ready")
            session.pause()
            session.seek(30)
            session.close()
        self.assertTrue(any('"pause"' in text for text in process.stdin.writes))
        self.assertTrue(any('"seek"' in text and "30.000" in text for text in process.stdin.writes))


class _WaitFailsOnceProcess(_ScriptedProcess):
    """Simulates terminate() not being enough, so close() falls back to
    kill() - and tracks whether it then reaps the killed process."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wait_calls = 0
        self.killed = False

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.wait_calls == 1:
            raise subprocess.TimeoutExpired(cmd="helper", timeout=timeout)
        self.returncode = -9
        return -9

    def kill(self):
        self.killed = True


class TestMediaHelperSessionRobustness(unittest.TestCase):
    def test_stderr_tail_is_included_in_the_timeout_error(self):
        # An OS pipe fills at ~64KB; if nothing drains stderr, the
        # helper's next write to it blocks and the session just hangs
        # with no explanation. Draining it also means a real failure
        # gets to explain itself instead of a bare "timed out".
        process = _ScriptedProcess(['{"type":"hello","sdp":"client"}\n'], {})
        process.stderr = ["gst warning: no encoder", "fatal: negotiation failed"]
        with patch("kabin.media.native_helper_path", return_value="/tmp/helper"), patch(
            "kabin.media.subprocess.Popen", return_value=process
        ):
            session = MediaHelperSession("client")
            session._stderr_reader.join(timeout=1)
            with self.assertRaisesRegex(MediaHelperError, "negotiation failed"):
                session.wait("offer", timeout=0.05)
            session.close()

    def test_exited_error_includes_stderr_tail(self):
        process = _ScriptedProcess([], {})
        process.stderr = ["core dumped"]
        process.returncode = 1
        with patch("kabin.media.native_helper_path", return_value="/tmp/helper"), patch(
            "kabin.media.subprocess.Popen", return_value=process
        ):
            session = MediaHelperSession("client")
            session._stderr_reader.join(timeout=1)
            with self.assertRaisesRegex(MediaHelperError, "core dumped"):
                session.wait("hello", timeout=0.05)

    def test_close_reaps_the_process_after_a_kill_fallback(self):
        process = _WaitFailsOnceProcess(['{"type":"hello","sdp":"client"}\n'], {})
        with patch("kabin.media.native_helper_path", return_value="/tmp/helper"), patch(
            "kabin.media.subprocess.Popen", return_value=process
        ):
            session = MediaHelperSession("client")
            session.close()
        self.assertTrue(process.killed)
        self.assertEqual(process.wait_calls, 2)


if __name__ == "__main__":
    unittest.main()
