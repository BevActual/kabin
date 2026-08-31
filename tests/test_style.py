import unittest

from kabin.style import build_stylesheet


class TestStyle(unittest.TestCase):
    def test_uses_kabin_owned_palette(self):
        stylesheet = build_stylesheet()
        self.assertIn("@define-color accent_color #ffb454", stylesheet)
        self.assertIn("@define-color window_bg_color #101217", stylesheet)
        self.assertNotIn("omarchy", stylesheet.casefold())
        self.assertIn(".kabin-art-landscape", stylesheet)
        self.assertIn(".kabin-art-square", stylesheet)
        self.assertIn(".kabin-hero", stylesheet)
        self.assertIn(".kabin-browse-card", stylesheet)
        self.assertIn(".kabin-shortcut-key", stylesheet)
        self.assertIn(".kabin-player", stylesheet)
        self.assertIn(".kabin-progress", stylesheet)
        self.assertIn(".kabin-now-chip", stylesheet)
        self.assertIn(".kabin-tile-playing", stylesheet)
        self.assertIn("0 22px 40px", stylesheet)
        self.assertIn("alpha(white, 0.88)", stylesheet)
        self.assertIn(".kabin-track-current", stylesheet)
        self.assertIn(".kabin-filter-chip", stylesheet)
        self.assertIn(".kabin-hero-play", stylesheet)


if __name__ == "__main__":
    unittest.main()
