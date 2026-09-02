import struct
import unittest

from kabin.gamepad import (
    ABS_HAT0X,
    ABS_HAT0Y,
    ABS_X,
    ABS_Y,
    BTN_EAST,
    BTN_SOUTH,
    BTN_START,
    BTN_THUMBL,
    EVENT_FORMAT,
    EVENT_SIZE,
    EV_ABS,
    EV_KEY,
    axis_to_action,
    button_to_action,
    cycle_index,
    move_grid_index,
    unpack_events,
)


class TestGamepad(unittest.TestCase):
    def test_unpacks_64bit_evdev_frames(self):
        frame = struct.pack("llHHi", 1, 2, EV_KEY, BTN_SOUTH, 1)
        self.assertEqual(unpack_events(frame), [(EV_KEY, BTN_SOUTH, 1)])

    def test_event_size_follows_the_running_abi(self):
        # Regression: the layout used to be picked by matching the read
        # length against hardcoded sizes (24, then 16), which is ambiguous
        # for any length divisible by both and mismatched native struct
        # sizing entirely on 32-bit userspace. The kernel's input_event
        # uses word-sized time fields, which is exactly what native "l"
        # gives us.
        self.assertEqual(EVENT_SIZE, struct.calcsize(EVENT_FORMAT))

    def test_unpacks_a_multi_event_read(self):
        # 48 bytes on a 64-bit ABI is unambiguously two events; the old
        # size-guessing table could read it as three 16-byte ones.
        blob = struct.pack("llHHi", 1, 2, EV_KEY, BTN_SOUTH, 1) + struct.pack(
            "llHHi", 3, 4, EV_ABS, ABS_HAT0X, -1
        )
        self.assertEqual(len(blob), EVENT_SIZE * 2)
        self.assertEqual(
            unpack_events(blob),
            [(EV_KEY, BTN_SOUTH, 1), (EV_ABS, ABS_HAT0X, -1)],
        )

    def test_ragged_and_empty_reads_are_ignored(self):
        self.assertEqual(unpack_events(b""), [])
        self.assertEqual(unpack_events(b"\x00" * (EVENT_SIZE - 1)), [])
        self.assertEqual(unpack_events(b"\x00" * (EVENT_SIZE + 3)), [])

    def test_face_buttons_use_xbox_layout(self):
        self.assertEqual(button_to_action(BTN_SOUTH, 1), "confirm")
        self.assertEqual(button_to_action(BTN_EAST, 1), "back")
        self.assertEqual(button_to_action(BTN_START, 1), "options")
        self.assertEqual(button_to_action(BTN_THUMBL, 1), "random")
        self.assertIsNone(button_to_action(BTN_SOUTH, 0))

    def test_hat_and_stick_become_directions(self):
        self.assertEqual(axis_to_action(ABS_HAT0X, -1), "left")
        self.assertEqual(axis_to_action(ABS_HAT0Y, 1), "down")
        self.assertEqual(axis_to_action(ABS_X, -24000), "left")
        self.assertEqual(axis_to_action(ABS_Y, 800), None)
        self.assertIsNone(axis_to_action(ABS_HAT0X, 0))

    def test_grid_left_edge_leaves_the_grid(self):
        self.assertIsNone(move_grid_index(0, 10, 4, "left"))
        self.assertIsNone(move_grid_index(4, 10, 4, "left"))
        self.assertEqual(move_grid_index(5, 10, 4, "left"), 4)
        self.assertEqual(move_grid_index(1, 10, 4, "up"), 0)
        self.assertEqual(move_grid_index(1, 10, 4, "down"), 5)
        self.assertEqual(move_grid_index(9, 10, 4, "right"), 9)

    def test_category_wraps(self):
        self.assertEqual(cycle_index(0, 3, -1), 2)
        self.assertEqual(cycle_index(2, 3, 1), 0)


if __name__ == "__main__":
    unittest.main()
