"""Track an emulator (or other launched program) while it runs.

Launching used to be fire-and-forget: Kabin called Popen and never heard
from the process again. That meant an emulator that rejected its flags or
couldn't find a BIOS died silently behind the window, the Play button
could start a second copy, and nothing knew how long you actually played.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

# An emulator that exits this quickly with a non-zero status almost
# certainly never showed a game: bad flags, missing BIOS, unreadable ROM.
QUICK_EXIT_SECONDS = 5.0

# Sessions shorter than this don't count as play time; they're the
# "launched the wrong thing and quit" case.
MIN_RECORDED_SECONDS = 30.0


@dataclass
class PlaySession:
    game_id: str
    title: str
    process: object  # anything with poll() -> returncode | None
    started_at: float = field(default_factory=time.monotonic)

    def elapsed(self, now: float | None = None) -> float:
        return max(0.0, (time.monotonic() if now is None else now) - self.started_at)

    def returncode(self):
        return self.process.poll()

    @property
    def running(self) -> bool:
        return self.returncode() is None


def quick_failure_message(title: str, returncode, elapsed: float) -> str | None:
    """Toast for a launch that clearly never got going, else None.

    A clean exit (0) inside the window is left alone: some emulators fork
    and return immediately, and a user closing a game fast is not an error.
    """
    if returncode is None or returncode == 0 or elapsed >= QUICK_EXIT_SECONDS:
        return None
    if returncode < 0:
        return f"{title} was stopped by signal {-returncode} right after launch."
    return (
        f"{title} closed right away (exit code {returncode}). "
        "Check the emulator and BIOS in Settings › Emulation."
    )


def recordable_seconds(elapsed: float) -> int:
    return int(elapsed) if elapsed >= MIN_RECORDED_SECONDS else 0


def format_play_time(seconds: float) -> str:
    """'42m', '3h 05m', '1h' - short enough for the details meta line."""
    total = int(seconds)
    if total < 60:
        return ""
    hours, remainder = divmod(total, 3600)
    minutes = remainder // 60
    if hours == 0:
        return f"{minutes}m"
    if minutes == 0:
        return f"{hours}h"
    return f"{hours}h {minutes:02d}m"
