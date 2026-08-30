import unittest

from kabin.style import build_stylesheet


class TestStyle(unittest.TestCase):
    def test_uses_kabin_owned_palette(self):
        stylesheet = build_stylesheet()
        self.assertIn("@define-color accent_color #ffb454", stylesheet)
        self.assertIn("@define-color window_bg_color #101217", stylesheet)
        self.assertNotIn("omarchy", stylesheet.casefold())


if __name__ == "__main__":
    unittest.main()
