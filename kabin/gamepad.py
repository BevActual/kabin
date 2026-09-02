from __future__ import annotations

import os
import select
import struct
import threading
import time
from pathlib import Path

EV_KEY = 0x01
EV_ABS = 0x03

BTN_SOUTH = 0x130
BTN_EAST = 0x131
BTN_NORTH = 0x133
BTN_WEST = 0x134
BTN_TL = 0x136
BTN_TR = 0x137
BTN_SELECT = 0x13A
BTN_START = 0x13B
BTN_MODE = 0x13C
BTN_THUMBL = 0x13D

ABS_X = 0x00
ABS_Y = 0x01
ABS_HAT0X = 0x10
ABS_HAT0Y = 0x11

STICK_DEADZONE = 20000
REPEATABLE = {"left", "right", "up", "down"}
INITIAL_REPEAT = 0.34
REPEAT_RATE = 0.12

BUTTON_ACTIONS = {
    BTN_SOUTH: "confirm",
    BTN_EAST: "back",
    BTN_NORTH: "extra",
    BTN_WEST: "search",
    BTN_TL: "prev",
    BTN_TR: "next",
    BTN_SELECT: "search",
    BTN_START: "options",
    # Guide / Mode is free of the Start→Settings mapping and is the
    # natural "reload the cabinet" button on a couch pad.
    BTN_MODE: "refresh",
    BTN_THUMBL: "random",
}

# The kernel's struct input_event is two word-sized time fields followed
# by __u16 type, __u16 code, __s32 value. Python's native "l" is exactly
# C's long, so calcsize matches the running ABI (24 bytes on 64-bit, 16 on
# 32-bit) rather than guessing the layout from how many bytes a read
# happened to return - which was ambiguous at any length divisible by both
# sizes, and outright broke on 32-bit userspace where the hardcoded 24
# never matched native sizing.
EVENT_FORMAT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)


def unpack_events(blob: bytes) -> list[tuple[int, int, int]]:
    """Turn raw evdev bytes into (type, code, value) tuples."""
    if not blob or len(blob) % EVENT_SIZE:
        return []
    return [
        struct.unpack(EVENT_FORMAT, blob[offset : offset + EVENT_SIZE])[2:]
        for offset in range(0, len(blob), EVENT_SIZE)
    ]


def axis_to_action(code: int, value: int, deadzone: int = STICK_DEADZONE) -> str | None:
    if code in (ABS_HAT0X, ABS_X):
        if code == ABS_HAT0X:
            if value < 0:
                return "left"
            if value > 0:
                return "right"
            return None
        if value <= -deadzone:
            return "left"
        if value >= deadzone:
            return "right"
        return None
    if code in (ABS_HAT0Y, ABS_Y):
        if code == ABS_HAT0Y:
            if value < 0:
                return "up"
            if value > 0:
                return "down"
            return None
        if value <= -deadzone:
            return "up"
        if value >= deadzone:
            return "down"
        return None
    return None


def button_to_action(code: int, value: int) -> str | None:
    if value != 1:
        return None
    return BUTTON_ACTIONS.get(code)


def move_grid_index(index: int, count: int, columns: int, action: str) -> int | None:
    """Move inside a grid. None means the action left the left edge."""
    if count <= 0:
        return None
    columns = max(1, columns)
    index = max(0, min(count - 1, index))
    if action == "left":
        if index % columns == 0:
            return None
        return index - 1
    if action == "right":
        return min(count - 1, index + 1)
    if action == "up":
        return max(0, index - columns)
    if action == "down":
        return min(count - 1, index + columns)
    return index


def cycle_index(index: int, count: int, delta: int) -> int:
    if count <= 0:
        return 0
    return (index + delta) % count


def joystick_event_paths(input_dir: Path = Path("/dev/input/by-id")) -> list[Path]:
    try:
        return sorted(input_dir.glob("*-event-joystick"))
    except OSError:
        return []


class GamepadMonitor:
    """Read Linux joystick evdev nodes and emit cabinet actions."""

    def __init__(self, on_action, input_dir: Path | None = None):
        self._on_action = on_action
        self._input_dir = input_dir or Path("/dev/input/by-id")
        self._stop = threading.Event()
        self._held: dict[str, float] = {}
        self._last_repeat: dict[str, float] = {}
        self._axis_actions: dict[int, str | None] = {}
        self._has_pad = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @property
    def connected(self) -> bool:
        return self._has_pad

    def close(self) -> None:
        self._stop.set()

    def _emit(self, action: str, now: float, repeating: bool = False) -> None:
        if action in REPEATABLE:
            if not repeating:
                self._held[action] = now
                self._last_repeat[action] = now
            self._on_action(action)
            return
        self._on_action(action)

    def _release(self, action: str | None) -> None:
        if action:
            self._held.pop(action, None)
            self._last_repeat.pop(action, None)

    def _handle_event(self, etype: int, code: int, value: int, now: float) -> None:
        if etype == EV_KEY:
            if value == 0:
                self._release(BUTTON_ACTIONS.get(code))
                return
            action = button_to_action(code, value)
            if action:
                self._emit(action, now)
            return
        if etype != EV_ABS:
            return
        action = axis_to_action(code, value)
        previous = self._axis_actions.get(code)
        if action == previous:
            return
        self._release(previous)
        self._axis_actions[code] = action
        if action:
            self._emit(action, now)

    def _fire_repeats(self, now: float) -> None:
        for action, started in list(self._held.items()):
            if now - started < INITIAL_REPEAT:
                continue
            if now - self._last_repeat.get(action, started) >= REPEAT_RATE:
                self._last_repeat[action] = now
                self._emit(action, now, repeating=True)

    def _open_devices(self, current: dict[int, Path]) -> dict[int, Path]:
        known = {path for path in current.values()}
        opened = dict(current)
        for path in joystick_event_paths(self._input_dir):
            if path in known:
                continue
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                continue
            opened[fd] = path
            self._has_pad = True
        return opened

    def _run(self) -> None:
        devices: dict[int, Path] = {}
        last_scan = 0.0
        while not self._stop.is_set():
            now = time.monotonic()
            if now - last_scan >= 2:
                devices = self._open_devices(devices)
                last_scan = now
            if not devices:
                self._stop.wait(0.35)
                continue
            try:
                readable, _, _ = select.select(list(devices), [], [], 0.05)
            except (OSError, ValueError):
                for fd in list(devices):
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                devices = {}
                continue
            for fd in readable:
                try:
                    blob = os.read(fd, EVENT_SIZE * 32)
                except OSError:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    devices.pop(fd, None)
                    continue
                for etype, code, value in unpack_events(blob):
                    self._handle_event(etype, code, value, time.monotonic())
            self._fire_repeats(time.monotonic())
        for fd in devices:
            try:
                os.close(fd)
            except OSError:
                pass
