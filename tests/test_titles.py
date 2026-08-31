import unittest

from kabin.titles import clean_track_title, parse_media_name, restore_leading_article, track_sort_key


class TestTitles(unittest.TestCase):
    def test_parses_calibre_book_names(self):
        chamber = parse_media_name(
            "Harry Potter and the Chamber of Secrets -- J_ K_ Rowling -- 1999.epub",
            "book",
        )
        self.assertEqual(chamber.title, "Harry Potter and the Chamber of Secrets")
        self.assertEqual(chamber.creators, ("J.K. Rowling",))
        stone = parse_media_name(
            "Harry Potter and the Sorcerer's Stone -- by J_K_ Rowling -- Harry Potter.epub",
            "book",
        )
        self.assertEqual(stone.title, "Harry Potter and the Sorcerer's Stone")
        self.assertEqual(stone.creators, ("J.K. Rowling",))
        self.assertEqual(stone.series, "Harry Potter")

    def test_parses_comic_volume_and_drops_archive_junk(self):
        parsed = parse_media_name(
            "Naruto,Vol_1 Naruto Uzumaki(Colored) -- Kishimoto Masashi -- Jump Comics.epub",
            "comic",
        )
        self.assertEqual(parsed.title, "Naruto Uzumaki")
        self.assertEqual(parsed.creators, ("Kishimoto Masashi",))
        self.assertEqual(parsed.series, "Naruto")
        self.assertEqual(parsed.series_index, 1.0)
        junk = parse_media_name(
            "Some Book -- Author -- isbn 9780000000000 -- Anna's Archive.epub",
            "book",
        )
        self.assertEqual(junk.title, "Some Book")
        self.assertEqual(junk.creators, ("Author",))
        self.assertEqual(junk.series, "")

    def test_splits_artist_album_folders(self):
        parsed = parse_media_name(
            "King Gizzard & The Lizard Wizard with Mild High Club - Sketches Of Brunswick East",
            "music",
        )
        self.assertEqual(parsed.title, "Sketches Of Brunswick East")
        self.assertEqual(
            parsed.creators,
            ("King Gizzard & The Lizard Wizard with Mild High Club",),
        )
        various = parse_media_name(
            "Various Artists Label Sampler 2024-2026 - Balkan Railway",
            "music",
        )
        self.assertEqual(various.title, "Balkan Railway")
        self.assertEqual(various.creators, ("Various Artists",))

    def test_restores_trailing_articles(self):
        self.assertEqual(
            restore_leading_article("Legend of Zelda, The - Majora's Mask"),
            "The Legend of Zelda - Majora's Mask",
        )
        self.assertEqual(restore_leading_article("Hobbit, The"), "The Hobbit")
        self.assertEqual(restore_leading_article("Sketches Of Brunswick East"), "Sketches Of Brunswick East")

    def test_shortens_embedded_track_titles(self):
        self.assertEqual(
            clean_track_title(
                "King Gizzard - Sketches Of Brunswick East - 01 Sketches Of Brunswick East I.mp3",
                album="Sketches Of Brunswick East",
                artist="King Gizzard",
            ),
            "Sketches Of Brunswick East I",
        )
        self.assertEqual(
            clean_track_title("Aspirin Moon - Balkan Railway - 08 Artificial Emotions.mp3"),
            "Artificial Emotions",
        )
        self.assertEqual(clean_track_title("01 So What.flac"), "So What")
        self.assertEqual(
            clean_track_title("Svetlost - Balkan Railway - 03 R+J (for Miliana Lenak).mp3"),
            "R+J (for Miliana Lenak)",
        )

    def test_sorts_album_tracks_by_number(self):
        from pathlib import Path

        late = Path("Aspirin Moon - Balkan Railway - 08 Artificial Emotions.mp3")
        early = Path("AUM - Balkan Railway - 04 Night Train.mp3")
        self.assertLess(track_sort_key(early), track_sort_key(late))


if __name__ == "__main__":
    unittest.main()
