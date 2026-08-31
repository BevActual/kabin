import unittest

from kabin.models import Game, LibraryItem


class TestLibraryItem(unittest.TestCase):
    def test_book_organization_keeps_type_format_and_category_separate(self):
        book = LibraryItem(
            id="book:the-hobbit",
            title="The Hobbit",
            source="books",
            media_type="book",
            media_format="ebook",
            category="fiction",
            genres=["fantasy"],
            creators=["J. R. R. Tolkien"],
            series="Middle-earth",
            series_index=1,
        )
        self.assertEqual(book.media_type, "book")
        self.assertEqual(book.media_format, "ebook")
        self.assertEqual(book.category, "fiction")
        self.assertEqual(book.genres, ["fantasy"])

    def test_game_name_remains_compatible_with_generic_library_item(self):
        game = Game(id="steam:1", title="Game", source="steam")
        self.assertIsInstance(game, LibraryItem)
        self.assertEqual(game.media_type, "game")

    def test_search_text_includes_source_and_system(self):
        game = Game(
            id="roms:snes:game.sfc",
            title="Super Metroid",
            source="roms",
            subtitle="Super Nintendo",
            extra={"system": "snes"},
        )
        self.assertIn("super metroid", game.search_text)
        self.assertIn("snes", game.search_text)
        self.assertIn("roms", game.search_text)


if __name__ == "__main__":
    unittest.main()
