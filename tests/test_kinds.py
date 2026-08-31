import unittest

from kabin.kinds import CABINET_KIND, FOLDER_KINDS, count_noun, get_kind, kind_for
from kabin.models import LibraryItem


class TestMediaKinds(unittest.TestCase):
    def test_unknown_type_uses_cabinet_poster(self):
        self.assertIs(get_kind("nope"), CABINET_KIND)
        self.assertEqual(kind_for(LibraryItem(id="x", title="X", source="steam")).id, "game")

    def test_folder_kinds_have_extensions_and_verbs(self):
        verbs = {kind.id: kind.verb for kind in FOLDER_KINDS}
        self.assertEqual(verbs["book"], "Read")
        self.assertEqual(verbs["music"], "Listen")
        self.assertEqual(verbs["video"], "Watch")
        self.assertIn(".epub", get_kind("book").extensions)
        self.assertIn(".cbz", get_kind("comic").extensions)
        self.assertEqual(get_kind("music").shape, "square")
        self.assertEqual(get_kind("video").shape, "landscape")
        self.assertNotEqual(get_kind("music").accent, get_kind("video").accent)

    def test_count_noun_matches_kind(self):
        self.assertEqual(count_noun(1, get_kind("book")), "book")
        self.assertEqual(count_noun(2, get_kind("book")), "books")


if __name__ == "__main__":
    unittest.main()
