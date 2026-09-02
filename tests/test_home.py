import unittest
from types import SimpleNamespace

from kabin.home import (
    added_heading,
    continue_caption,
    continue_heading,
    continue_tile_scale,
    hero_meta_line,
    library_tile_scale,
    hero_uses_bleed,
    move_home_focus,
    opened_caption,
    show_library_sort,
    split_home_shelves,
)
from kabin.kinds import get_kind


def _item(item_id, kind, added_at=None, title=""):
    return SimpleNamespace(
        id=item_id,
        title=title or item_id,
        media_type=kind,
        extra={"added_at": added_at} if added_at else {},
    )


class TestHomeShelves(unittest.TestCase):
    def test_splits_continue_and_added_by_kind(self):
        books = [_item(f"book:{index}", "book", 20 - index) for index in range(5)]
        comic = _item("comic:1", "comic", 30)
        album = _item("music:1", "music", 40)
        games = [*books, comic, album]
        continue_rows, added_rows = split_home_shelves(
            games,
            ["comic:1", "book:0"],
            featured_id="comic:1",
        )
        continue_kinds = [kind.id for kind, _items in continue_rows]
        self.assertEqual(continue_kinds, ["book"])
        self.assertEqual([item.id for item in continue_rows[0][1]], ["book:0"])
        added = {kind.id: [item.id for item in items] for kind, items in added_rows}
        self.assertEqual(added["book"][0], "book:1")
        self.assertNotIn("music", added)
        self.assertNotIn("comic", added)

    def test_skips_recently_added_for_small_libraries(self):
        book = _item("book:1", "book", 20)
        older = _item("book:2", "book", 10)
        album = _item("music:1", "music", 40)
        _, added_rows = split_home_shelves(
            [book, older, album],
            ["book:1"],
            featured_id="book:1",
        )
        self.assertEqual(added_rows, [])

    def test_hero_meta_is_creator_not_a_verb(self):
        item = SimpleNamespace(creators=["J.K. Rowling"], series="Harry Potter")
        self.assertEqual(hero_meta_line(item), "J.K. Rowling · Harry Potter")

    def test_headings_name_the_library(self):
        self.assertEqual(continue_heading(get_kind("music")), "Continue · Music")
        self.assertEqual(added_heading(get_kind("book")), "Recently added · Books")

    def test_lonely_continue_tile_grows(self):
        self.assertEqual(continue_tile_scale(1), 1.28)
        self.assertEqual(continue_tile_scale(3), 1.0)

    def test_small_libraries_grow_and_hide_sort(self):
        self.assertEqual(library_tile_scale(1), 1.7)
        self.assertEqual(library_tile_scale(2), 1.5)
        self.assertEqual(library_tile_scale(5), 1.18)
        self.assertEqual(library_tile_scale(12), 1.0)
        self.assertFalse(show_library_sort(2))
        self.assertTrue(show_library_sort(6))

    def test_hero_bleed_is_only_for_widescreen(self):
        self.assertTrue(hero_uses_bleed(get_kind("video")))
        self.assertTrue(hero_uses_bleed(get_kind("tv")))
        self.assertFalse(hero_uses_bleed(get_kind("comic")))
        self.assertFalse(hero_uses_bleed(get_kind("music")))
        self.assertFalse(hero_uses_bleed(get_kind("book")))

    def test_continue_caption_prefers_resume(self):
        self.assertEqual(
            continue_caption(playing=True, clock="12:40"),
            "Now playing",
        )
        self.assertEqual(
            continue_caption(track=3, tracks=12, clock="1:02"),
            "Resume · Track 4 · 1:02",
        )
        self.assertEqual(continue_caption(clock="12:40"), "Resume · 12:40")
        self.assertEqual(
            opened_caption(1_700_000_000, now=1_700_000_000 + 90_000),
            "Opened yesterday",
        )
        self.assertEqual(
            continue_caption(opened_at=10, now=40, fallback="Last opened"),
            "Opened just now",
        )

    def test_home_focus_moves_and_exits_left(self):
        self.assertIsNone(move_home_focus([2, 4], 0, 0, "left"))
        self.assertEqual(move_home_focus([2, 4], 0, 0, "right"), (0, 1))
        self.assertEqual(move_home_focus([2, 4], 0, 1, "down"), (1, 1))
        self.assertEqual(move_home_focus([2, 4], 1, 3, "up"), (0, 1))
        self.assertEqual(move_home_focus([2, 4], 1, 3, "down"), (1, 3))


if __name__ == "__main__":
    unittest.main()
