import unittest

from kabin.browse import first_index_for_prefix, pick_random_index


class _FixedRng:
    def __init__(self, value):
        self.value = value

    def randbelow(self, count):
        return min(self.value, count - 1)


class TestBrowseHelpers(unittest.TestCase):
    def test_letter_jump_finds_first_match(self):
        titles = ["Celeste", "Hades", "Hollow Knight", "Ico"]
        self.assertEqual(first_index_for_prefix(titles, "h"), 1)
        self.assertEqual(first_index_for_prefix(titles, "H"), 1)
        self.assertIsNone(first_index_for_prefix(titles, "z"))

    def test_hash_jumps_to_numbered_title(self):
        titles = ["Celeste", "1942", "Ico"]
        self.assertEqual(first_index_for_prefix(titles, "#"), 1)

    def test_random_picker_stays_in_range(self):
        self.assertIsNone(pick_random_index(0))
        self.assertEqual(pick_random_index(4, rng=_FixedRng(2)), 2)


if __name__ == "__main__":
    unittest.main()
