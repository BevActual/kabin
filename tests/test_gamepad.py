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
