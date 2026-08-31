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
        self.assertIn(".kabin-hero-poster", stylesheet)
        self.assertIn(".kabin-hero-quiet", stylesheet)
        self.assertIn(".kabin-player", stylesheet)
        self.assertIn(".kabin-progress", stylesheet)
        self.assertIn(".kabin-now-chip", stylesheet)
        self.assertIn(".kabin-tile-playing", stylesheet)
        self.assertIn("0 0 0 2px", stylesheet)
        self.assertIn("alpha(white, 0.9)", stylesheet)
        self.assertIn("button.kabin-tile", stylesheet)
        self.assertIn("border-radius: 0;", stylesheet)
        self.assertIn(".kabin-hero-play:focus-visible", stylesheet)
        self.assertIn(".kabin-tile:focus-visible .kabin-tile-art", stylesheet)
        self.assertIn(".kabin-game-grid.kabin-nav-focus > child:selected .kabin-tile-art", stylesheet)
        self.assertIn(".kabin-track-current", stylesheet)
        self.assertIn(".kabin-filter-chip", stylesheet)
        self.assertIn(".kabin-hero-play", stylesheet)
        self.assertIn(".kabin-kicker", stylesheet)
        self.assertIn(".kabin-player-pause", stylesheet)
        self.assertIn(".kabin-details-kicker", stylesheet)
        self.assertIn(".kabin-cover-choice-art", stylesheet)
        self.assertIn(".kabin-content-page", stylesheet)
        self.assertIn(".kabin-game-scroller", stylesheet)
        self.assertIn("navigation-view-page", stylesheet)
        self.assertIn(".content-pane", stylesheet)
        self.assertIn("child.activatable:selected", stylesheet)
        self.assertIn(".kabin-backdrop-library", stylesheet)
        self.assertIn("transform: scale(1.06)", stylesheet)
        self.assertIn(".kabin-shelf-row", stylesheet)
        self.assertIn("gridview > child:selected", stylesheet)


if __name__ == "__main__":
    unittest.main()
