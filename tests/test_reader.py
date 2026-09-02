import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kabin.config import Config
from kabin.playback import progress_for, save_progress
from kabin.reader import (
    ComicArchivePages,
    ComicTarPages,
    ComicZipPages,
    EpubPages,
    FB2Pages,
    PdfPages,
    TextPages,
    apply_reader_webview_settings,
    open_comic_pages,
    open_reader_pages,
    parse_xml,
    prune_cache,
    prune_remote_read_cache,
    remote_read_cache_root,
    opens_in_kabin_reader,
    reader_backend_for,
    reader_uri_allowed,
    remote_read_cache_path,
    remote_read_suffix,
    resume_page,
    resume_scroll,
    save_page_progress,
    step_adjustment,
    sync_progress_from_remote,
    uses_tap_zones,
)

_BSDTAR_AVAILABLE = shutil.which("bsdtar") is not None

_CONTAINER_XML = b"""<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

_CONTENT_OPF = b"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <manifest>
    <item id="chap1" href="chap1.xhtml" media-type="application/xhtml+xml"/>
    <item id="chap2" href="chap2.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="chap1"/>
    <itemref idref="chap2"/>
  </spine>
</package>
"""


def _write_epub(path: Path, extra_names=()):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", _CONTAINER_XML)
        archive.writestr("OEBPS/content.opf", _CONTENT_OPF)
        archive.writestr("OEBPS/chap1.xhtml", "<html><body>Chapter one</body></html>")
        archive.writestr("OEBPS/chap2.xhtml", "<html><body>Chapter two</body></html>")
        for name in extra_names:
            archive.writestr(name, "malicious payload")


_CONTENT_OPF_WITH_NAV = b"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <manifest>
    <item id="chap1" href="chap1.xhtml" media-type="application/xhtml+xml"/>
    <item id="chap2" href="chap2.xhtml" media-type="application/xhtml+xml"/>
    <item id="chap3" href="chap3.xhtml" media-type="application/xhtml+xml"/>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  </manifest>
  <spine>
    <itemref idref="chap1"/>
    <itemref idref="chap2"/>
    <itemref idref="chap3"/>
  </spine>
</package>
"""

_NAV_XHTML = b"""<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <body>
    <nav epub:type="toc">
      <ol>
        <li><a href="chap1.xhtml">Chapter One</a></li>
        <li><a href="chap2.xhtml">Chapter Two</a>
          <ol><li><a href="chap3.xhtml#sec1">Chapter Three, Section One</a></li></ol>
        </li>
      </ol>
    </nav>
  </body>
</html>
"""


def _write_epub_with_nav(path: Path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", _CONTAINER_XML)
        archive.writestr("OEBPS/content.opf", _CONTENT_OPF_WITH_NAV)
        archive.writestr("OEBPS/nav.xhtml", _NAV_XHTML)
        archive.writestr("OEBPS/chap1.xhtml", "<html><body>Chapter one</body></html>")
        archive.writestr("OEBPS/chap2.xhtml", "<html><body>Chapter two</body></html>")
        archive.writestr("OEBPS/chap3.xhtml", "<html><body>Chapter three</body></html>")


_CONTENT_OPF_WITH_NCX = b"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <manifest>
    <item id="chap1" href="chap1.xhtml" media-type="application/xhtml+xml"/>
    <item id="chap2" href="chap2.xhtml" media-type="application/xhtml+xml"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="chap1"/>
    <itemref idref="chap2"/>
  </spine>
</package>
"""

_TOC_NCX = b"""<?xml version="1.0"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/">
  <navMap>
    <navPoint id="np1">
      <navLabel><text>Chapter One</text></navLabel>
      <content src="chap1.xhtml"/>
      <navPoint id="np1a">
        <navLabel><text>Chapter One, cont.</text></navLabel>
        <content src="chap1.xhtml#more"/>
      </navPoint>
    </navPoint>
    <navPoint id="np2">
      <navLabel><text>Chapter Two</text></navLabel>
      <content src="chap2.xhtml"/>
    </navPoint>
  </navMap>
</ncx>
"""


def _write_epub_with_ncx(path: Path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", _CONTAINER_XML)
        archive.writestr("OEBPS/content.opf", _CONTENT_OPF_WITH_NCX)
        archive.writestr("OEBPS/toc.ncx", _TOC_NCX)
        archive.writestr("OEBPS/chap1.xhtml", "<html><body>Chapter one</body></html>")
        archive.writestr("OEBPS/chap2.xhtml", "<html><body>Chapter two</body></html>")

_MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 100] >>endobj
4 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 100] >>endobj
xref
0 5
0000000000 65535 f
trailer<< /Size 5 /Root 1 0 R >>
startxref
0
%%EOF
"""


def _item(media_type: str, path: Path):
    return SimpleNamespace(extra={"path": str(path)}, media_type=media_type)


class TestReaderBackend(unittest.TestCase):
    def test_pdf_and_epub_need_the_right_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            book_pdf = Path(tmp) / "book.pdf"
            book_pdf.write_bytes(b"%PDF-1.4\n")
            self.assertEqual(reader_backend_for(_item("book", book_pdf)), "pdf")
            self.assertTrue(opens_in_kabin_reader(_item("book", book_pdf)))

            game_pdf = Path(tmp) / "manual.pdf"
            game_pdf.write_bytes(b"%PDF-1.4\n")
            self.assertIsNone(reader_backend_for(_item("game", game_pdf)))

    def test_epub_gated_on_webkit_availability(self):
        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / "book.epub"
            epub.write_bytes(b"PK\x03\x04")
            with patch("kabin.reader._webkit_available", return_value=False):
                self.assertIsNone(reader_backend_for(_item("book", epub)))
                self.assertFalse(opens_in_kabin_reader(_item("comic", epub)))
            with patch("kabin.reader._webkit_available", return_value=True):
                self.assertEqual(reader_backend_for(_item("book", epub)), "epub")
                self.assertEqual(reader_backend_for(_item("comic", epub)), "epub")

    def test_fb2_gated_on_webkit_availability(self):
        with tempfile.TemporaryDirectory() as tmp:
            fb2 = Path(tmp) / "book.fb2"
            fb2.write_bytes(b"<FictionBook/>")
            with patch("kabin.reader._webkit_available", return_value=False):
                self.assertIsNone(reader_backend_for(_item("book", fb2)))
            with patch("kabin.reader._webkit_available", return_value=True):
                self.assertEqual(reader_backend_for(_item("book", fb2)), "fb2")

    def test_cbz_and_cbt_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            cbz = Path(tmp) / "issue.cbz"
            with zipfile.ZipFile(cbz, "w") as archive:
                archive.writestr("001.jpg", b"a")
            self.assertEqual(reader_backend_for(_item("comic", cbz)), "comic-zip")

            cbt = Path(tmp) / "issue.cbt"
            with tarfile.open(cbt, "w") as archive:
                pass
            self.assertEqual(reader_backend_for(_item("comic", cbt)), "comic-tar")

    def test_unsupported_format_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            mobi = Path(tmp) / "book.mobi"
            mobi.write_bytes(b"x")
            self.assertIsNone(reader_backend_for(_item("book", mobi)))
            self.assertFalse(opens_in_kabin_reader(_item("book", mobi)))

            missing = _item("book", Path(tmp) / "missing.pdf")
            self.assertIsNone(reader_backend_for(missing))

    def test_txt_always_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            txt = Path(tmp) / "book.txt"
            txt.write_text("hello")
            self.assertEqual(reader_backend_for(_item("book", txt)), "text")

    def test_cb7_gated_on_bsdtar_availability(self):
        with tempfile.TemporaryDirectory() as tmp:
            cb7 = Path(tmp) / "issue.cb7"
            cb7.write_bytes(b"7z\xbc\xaf\x27\x1c")
            with patch("kabin.reader._bsdtar_available", return_value=False):
                self.assertIsNone(reader_backend_for(_item("comic", cb7)))
            with patch("kabin.reader._bsdtar_available", return_value=True):
                self.assertEqual(reader_backend_for(_item("comic", cb7)), "comic-7z")

    def test_cbr_gated_on_bsdtar_availability(self):
        with tempfile.TemporaryDirectory() as tmp:
            cbr = Path(tmp) / "issue.cbr"
            cbr.write_bytes(b"Rar!\x1a\x07\x00")
            with patch("kabin.reader._bsdtar_available", return_value=False):
                self.assertIsNone(reader_backend_for(_item("comic", cbr)))
            with patch("kabin.reader._bsdtar_available", return_value=True):
                self.assertEqual(reader_backend_for(_item("comic", cbr)), "comic-rar")


class TestComicPages(unittest.TestCase):
    def test_cbz_pages_are_naturally_sorted_and_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            cbz = Path(tmp) / "issue.cbz"
            with zipfile.ZipFile(cbz, "w") as archive:
                archive.writestr("page10.jpg", b"ten")
                archive.writestr("page2.jpg", b"two")
                archive.writestr("page1.jpg", b"one")
                archive.writestr("covers/notes.txt", b"skip me")
                archive.writestr("__MACOSX/page1.jpg", b"skip me too")
            pages = open_comic_pages(cbz, "comic-zip")
            self.assertIsInstance(pages, ComicZipPages)
            self.assertEqual(pages.names, ["page1.jpg", "page2.jpg", "page10.jpg"])
            self.assertEqual(len(pages), 3)
            self.assertEqual(pages.page_bytes(0), b"one")
            self.assertEqual(pages.page_bytes(2), b"ten")
            pages.close()

    def test_cbt_pages_are_naturally_sorted_and_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "page10.png").write_bytes(b"ten")
            (src / "page2.png").write_bytes(b"two")
            (src / "page1.png").write_bytes(b"one")
            (src / "readme.txt").write_bytes(b"skip")
            cbt = Path(tmp) / "issue.cbt"
            with tarfile.open(cbt, "w") as archive:
                for child in sorted(src.iterdir()):
                    archive.add(child, arcname=child.name)
            pages = open_comic_pages(cbt, "comic-tar")
            self.assertIsInstance(pages, ComicTarPages)
            self.assertEqual(pages.names, ["page1.png", "page2.png", "page10.png"])
            self.assertEqual(pages.page_bytes(1), b"two")
            pages.close()

    def test_unknown_backend_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                open_comic_pages(Path(tmp) / "nope", "comic-ace")


@unittest.skipUnless(_BSDTAR_AVAILABLE, "bsdtar not installed")
class TestComicArchivePages(unittest.TestCase):
    def test_glob_characters_in_page_names_extract_literally(self):
        # Regression: bsdtar treats the trailing argument as a shell-style
        # pattern, so a page named "page*.jpg" matched every page and the
        # reader was handed all of them concatenated - one corrupt image.
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "page1.jpg").write_bytes(b"AAAA")
            (src / "page2.jpg").write_bytes(b"BBBB")
            (src / "page*.jpg").write_bytes(b"GLOB")
            (src / "page?.jpg").write_bytes(b"QUES")
            (src / "page[1].jpg").write_bytes(b"BRAK")
            cb7 = Path(tmp) / "issue.cb7"
            subprocess.run(
                ["bsdtar", "-cf", str(cb7), "--format=7zip", "-C", str(src)]
                + sorted(p.name for p in src.iterdir()),
                check=True,
            )
            pages = open_reader_pages(cb7, "comic-7z")
            by_name = {name: pages.page_bytes(i) for i, name in enumerate(pages.names)}
            pages.close()

        self.assertEqual(by_name["page1.jpg"], b"AAAA")
        self.assertEqual(by_name["page2.jpg"], b"BBBB")
        self.assertEqual(by_name["page*.jpg"], b"GLOB")
        self.assertEqual(by_name["page?.jpg"], b"QUES")
        self.assertEqual(by_name["page[1].jpg"], b"BRAK")

    def test_cb7_pages_are_naturally_sorted_and_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "page10.jpg").write_bytes(b"ten")
            (src / "page2.jpg").write_bytes(b"two")
            (src / "page1.jpg").write_bytes(b"one")
            (src / "notes.txt").write_bytes(b"skip")
            cb7 = Path(tmp) / "issue.cb7"
            subprocess.run(
                ["bsdtar", "-cf", str(cb7), "--format=7zip", "-C", str(src)]
                + sorted(p.name for p in src.iterdir()),
                check=True,
            )
            pages = open_reader_pages(cb7, "comic-7z")
            self.assertIsInstance(pages, ComicArchivePages)
            self.assertEqual(pages.names, ["page1.jpg", "page2.jpg", "page10.jpg"])
            self.assertEqual(len(pages), 3)
            self.assertEqual(pages.page_bytes(0), b"one")
            self.assertEqual(pages.page_bytes(2), b"ten")
            pages.close()

    def test_comic_rar_backend_dispatches_to_the_same_archive_reader(self):
        # No tool on this system can *write* a real RAR file (libarchive's
        # RAR support is read-only, matching how it can legally ship a
        # from-scratch RAR decompressor but not an encoder), so this can't
        # exercise actual RAR bytes end-to-end. What it does confirm: the
        # "comic-rar" backend string routes to the same bsdtar-backed
        # reader as "comic-7z" — bsdtar itself detects the real format
        # from content, not from which backend name Kabin passed in.
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "page1.jpg").write_bytes(b"one")
            cb7 = Path(tmp) / "issue.cb7"
            subprocess.run(
                ["bsdtar", "-cf", str(cb7), "--format=7zip", "-C", str(src), "page1.jpg"],
                check=True,
            )
            pages = open_reader_pages(cb7, "comic-rar")
            self.assertIsInstance(pages, ComicArchivePages)
            self.assertEqual(pages.page_bytes(0), b"one")
            pages.close()



class TestReaderPageCache(unittest.TestCase):
    @unittest.skipUnless(_BSDTAR_AVAILABLE, "bsdtar not installed")
    def test_comic_archive_pages_cache_repeated_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "page1.jpg").write_bytes(b"one")
            (src / "page2.jpg").write_bytes(b"two")
            cb7 = Path(tmp) / "issue.cb7"
            subprocess.run(
                ["bsdtar", "-cf", str(cb7), "--format=7zip", "-C", str(src), "page1.jpg", "page2.jpg"],
                check=True,
            )
            pages = open_reader_pages(cb7, "comic-7z")
            calls = {"n": 0}
            from kabin import reader as reader_mod

            original = reader_mod._bsdtar_extract

            def counting_extract(path, member):
                calls["n"] += 1
                return original(path, member)

            with patch.object(reader_mod, "_bsdtar_extract", side_effect=counting_extract):
                first = pages.page_bytes(0)
                second = pages.page_bytes(0)
                third = pages.page_bytes(1)
            pages.close()
            self.assertEqual(first, second)
            self.assertEqual(first, b"one")
            self.assertEqual(third, b"two")
            self.assertEqual(calls["n"], 2)

    def test_pdf_pages_cache_by_width(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "book.pdf"
            pdf.write_bytes(_MINIMAL_PDF)
            pages = open_reader_pages(pdf, "pdf")
            renders = {"n": 0}
            real_get_page = pages._document.get_page

            def counting_get_page(index):
                renders["n"] += 1
                return real_get_page(index)

            pages._document.get_page = counting_get_page
            a = pages.page_bytes(0, target_width=80)
            b = pages.page_bytes(0, target_width=80)
            c = pages.page_bytes(0, target_width=120)
            pages.close()
            self.assertEqual(a, b)
            self.assertTrue(a.startswith(b"\x89PNG"))
            self.assertTrue(c.startswith(b"\x89PNG"))
            self.assertEqual(renders["n"], 2)



class TestTextPages(unittest.TestCase):
    def test_txt_is_a_single_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            txt = Path(tmp) / "book.txt"
            txt.write_text("Once upon a time.")
            pages = open_reader_pages(txt, "text")
            self.assertIsInstance(pages, TextPages)
            self.assertEqual(len(pages), 1)
            self.assertEqual(pages.page_bytes(0), b"Once upon a time.")
            with self.assertRaises(IndexError):
                pages.page_bytes(1)
            pages.close()


class TestPdfPages(unittest.TestCase):
    def test_pdf_pages_render_to_png_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "book.pdf"
            pdf.write_bytes(_MINIMAL_PDF)
            pages = open_reader_pages(pdf, "pdf")
            self.assertIsInstance(pages, PdfPages)
            self.assertEqual(len(pages), 2)
            data = pages.page_bytes(0, target_width=80)
            self.assertTrue(data.startswith(b"\x89PNG"))
            pages.close()


class TestEpubToc(unittest.TestCase):
    def test_epub3_nav_toc_resolves_nested_entries_to_spine_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / "book.epub"
            _write_epub_with_nav(epub)
            cache_root = Path(tmp) / "epub-cache"
            with patch("kabin.reader.epub_cache_root", return_value=cache_root):
                pages = open_reader_pages(epub, "epub")
                self.assertEqual(
                    pages.toc,
                    [
                        {"title": "Chapter One", "index": 0},
                        {"title": "Chapter Two", "index": 1},
                        {"title": "Chapter Three, Section One", "index": 2, "fragment": "sec1"},
                    ],
                )

    def test_ncx_toc_resolves_nested_entries_and_keeps_fragments(self):
        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / "book.epub"
            _write_epub_with_ncx(epub)
            cache_root = Path(tmp) / "epub-cache"
            with patch("kabin.reader.epub_cache_root", return_value=cache_root):
                pages = open_reader_pages(epub, "epub")
                self.assertEqual(
                    pages.toc,
                    [
                        {"title": "Chapter One", "index": 0},
                        {"title": "Chapter One, cont.", "index": 0, "fragment": "more"},
                        {"title": "Chapter Two", "index": 1},
                    ],
                )

    def test_missing_toc_is_an_empty_list_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / "book.epub"
            _write_epub(epub)
            cache_root = Path(tmp) / "epub-cache"
            with patch("kabin.reader.epub_cache_root", return_value=cache_root):
                pages = open_reader_pages(epub, "epub")
                self.assertEqual(pages.toc, [])

    def test_toc_is_cached_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / "book.epub"
            _write_epub_with_nav(epub)
            cache_root = Path(tmp) / "epub-cache"
            with patch("kabin.reader.epub_cache_root", return_value=cache_root):
                first = open_reader_pages(epub, "epub")
                second = EpubPages(epub)
                self.assertEqual(second.toc, first.toc)


class TestEpubPages(unittest.TestCase):
    def test_spine_order_and_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / "book.epub"
            _write_epub(epub)
            cache_root = Path(tmp) / "epub-cache"
            with patch("kabin.reader.epub_cache_root", return_value=cache_root):
                pages = open_reader_pages(epub, "epub")
                self.assertIsInstance(pages, EpubPages)
                self.assertEqual(len(pages), 2)
                self.assertEqual(pages.hrefs, ["OEBPS/chap1.xhtml", "OEBPS/chap2.xhtml"])
                self.assertIn("Chapter one", pages.page_bytes(0).decode())
                self.assertIn("Chapter two", pages.page_bytes(1).decode())
                base_uri = pages.page_base_uri(0)
                self.assertTrue(base_uri.startswith("file://"))
                self.assertTrue(base_uri.endswith("/"))
                oebps_dir = Path(base_uri.removeprefix("file://"))
                self.assertTrue((oebps_dir / "chap1.xhtml").is_file())
                pages.close()

    def test_extraction_is_cached_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / "book.epub"
            _write_epub(epub)
            cache_root = Path(tmp) / "epub-cache"
            with patch("kabin.reader.epub_cache_root", return_value=cache_root):
                first = open_reader_pages(epub, "epub")
                cached_files = list(cache_root.rglob("*"))
                self.assertTrue(cached_files)
                second = EpubPages(epub)
                self.assertEqual(second.hrefs, first.hrefs)

    def test_replacing_the_file_in_place_is_not_served_from_the_old_cache(self):
        # Regression: the cache key was the path alone, so replacing a book
        # in place (a better scan re-downloaded over it, Calibre rewriting
        # metadata, Syncthing pulling an update) kept serving the previous
        # extraction forever.
        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / "book.epub"
            _write_epub(epub)
            cache_root = Path(tmp) / "epub-cache"
            with patch("kabin.reader.epub_cache_root", return_value=cache_root):
                first = open_reader_pages(epub, "epub")
                self.assertIn("Chapter one", first.page_bytes(0).decode())

                # Same path, different contents (and a distinct mtime).
                epub.unlink()
                _write_epub_with_nav(epub)
                os.utime(epub, (1_000_000, 1_000_000))

                second = open_reader_pages(epub, "epub")
                self.assertEqual(len(second), 3)
                self.assertEqual(
                    [entry["title"] for entry in second.toc],
                    ["Chapter One", "Chapter Two", "Chapter Three, Section One"],
                )

    def test_zip_slip_entries_are_not_extracted_outside_the_cache_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / "evil.epub"
            _write_epub(epub, extra_names=["../../escaped.txt"])
            cache_root = Path(tmp) / "epub-cache"
            with patch("kabin.reader.epub_cache_root", return_value=cache_root):
                open_reader_pages(epub, "epub")
            self.assertFalse((Path(tmp) / "escaped.txt").exists())

    def test_missing_rootfile_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / "broken.epub"
            with zipfile.ZipFile(epub, "w") as archive:
                archive.writestr("META-INF/container.xml", "<container/>")
            cache_root = Path(tmp) / "epub-cache"
            with patch("kabin.reader.epub_cache_root", return_value=cache_root):
                with self.assertRaises(ValueError):
                    open_reader_pages(epub, "epub")


_FB2_BOOK = b"""<?xml version="1.0" encoding="UTF-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" xmlns:l="http://www.w3.org/1999/xlink">
  <body>
    <section>
      <title><p>Chapter One</p></title>
      <p>Hello <emphasis>world</emphasis>.</p>
      <image l:href="#cover.jpg"/>
    </section>
    <section>
      <title><p>Chapter Two</p></title>
      <p>Second chapter text.</p>
    </section>
  </body>
  <body name="notes">
    <section>
      <title><p>Footnotes</p></title>
      <p>Should not appear as a page.</p>
    </section>
  </body>
  <binary id="cover.jpg" content-type="image/jpeg">aGVsbG8=</binary>
</FictionBook>
"""

_FB2_EMPTY_BOOK = b"""<?xml version="1.0" encoding="UTF-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
  <body></body>
</FictionBook>
"""


class TestCachePruning(unittest.TestCase):
    def test_old_extractions_are_pruned_and_recent_ones_kept(self):
        # Regression: every EPUB/FB2 ever opened was extracted to its own
        # folder and never cleaned up - a second copy of the whole library
        # on disk, including books long since deleted and superseded copies
        # of books edited in place.
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp) / "epub-cache"
            books = Path(tmp) / "books"
            books.mkdir()

            opened = []
            with patch("kabin.reader.epub_cache_root", return_value=cache_root), patch(
                "kabin.reader.CACHED_BOOKS_KEPT", 3
            ):
                for index in range(6):
                    epub = books / f"book{index}.epub"
                    _write_epub(epub)
                    opened.append(open_reader_pages(epub, "epub")._root)

            surviving = {entry.name for entry in cache_root.iterdir() if entry.is_dir()}
            self.assertEqual(len(surviving), 3)
            # The three most recently opened books are the ones kept.
            self.assertEqual(surviving, {root.name for root in opened[-3:]})

    def test_pruning_a_missing_cache_root_is_harmless(self):
        with tempfile.TemporaryDirectory() as tmp:
            prune_cache(Path(tmp) / "not-created-yet")


class TestXmlSafety(unittest.TestCase):
    def test_entity_bomb_is_refused_rather_than_expanded(self):
        # "Billion laughs": ElementTree expands internal entities, so a few
        # hundred bytes of nested declarations become gigabytes in memory.
        # Ebooks routinely come from the internet, so refuse the file.
        bomb = b"""<?xml version="1.0"?>
<!DOCTYPE FictionBook [
  <!ENTITY a "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa">
  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
  <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
  <!ENTITY d "&c;&c;&c;&c;&c;&c;&c;&c;&c;&c;">
]>
<FictionBook><body><section><p>&d;</p></section></body></FictionBook>"""
        with self.assertRaisesRegex(ValueError, "entity declarations"):
            parse_xml(bomb)

    def test_ordinary_documents_still_parse(self):
        for doc in (
            b'<?xml version="1.0"?><FictionBook><p>caf&#233; &amp; cream</p></FictionBook>',
            b'<?xml version="1.0"?><!DOCTYPE html><html><body><p>hi</p></body></html>',
            b'<?xml version="1.0"?><!-- note --><FictionBook><p>x</p></FictionBook>',
            # Only the prolog is scanned, so content may mention the string.
            b'<?xml version="1.0"?><FictionBook><p>the &lt;!ENTITY bit</p></FictionBook>',
            b'<?xml version="1.0"?><FictionBook><p><![CDATA[<!ENTITY e "x">]]></p></FictionBook>',
        ):
            self.assertIsNotNone(parse_xml(doc))

    def test_an_fb2_bomb_is_refused_at_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            fb2 = Path(tmp) / "bomb.fb2"
            fb2.write_bytes(
                b'<?xml version="1.0"?>\n<!DOCTYPE FictionBook [\n'
                b'  <!ENTITY a "aaaaaaaaaa">\n'
                b'  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">\n]>\n'
                b"<FictionBook><body><section><p>&b;</p></section></body></FictionBook>"
            )
            cache_root = Path(tmp) / "fb2-cache"
            with patch("kabin.reader.fb2_cache_root", return_value=cache_root):
                with self.assertRaises(ValueError):
                    open_reader_pages(fb2, "fb2")


class TestFB2Pages(unittest.TestCase):
    def test_sections_become_pages_and_footnote_body_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            fb2 = Path(tmp) / "book.fb2"
            fb2.write_bytes(_FB2_BOOK)
            cache_root = Path(tmp) / "fb2-cache"
            with patch("kabin.reader.fb2_cache_root", return_value=cache_root):
                pages = open_reader_pages(fb2, "fb2")
                self.assertIsInstance(pages, FB2Pages)
                self.assertEqual(len(pages), 2)
                self.assertEqual(
                    pages.toc,
                    [{"title": "Chapter One", "index": 0}, {"title": "Chapter Two", "index": 1}],
                )
                page_one = pages.page_bytes(0).decode()
                self.assertIn("Hello <em>world</em>.", page_one)
                self.assertIn('<img src="cover.jpg">', page_one)
                self.assertNotIn("Footnotes", page_one + pages.page_bytes(1).decode())
                base_uri = pages.page_base_uri(0)
                image_path = Path(base_uri.removeprefix("file://")) / "cover.jpg"
                self.assertEqual(image_path.read_bytes(), b"hello")
                pages.close()

    def test_extraction_is_cached_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            fb2 = Path(tmp) / "book.fb2"
            fb2.write_bytes(_FB2_BOOK)
            cache_root = Path(tmp) / "fb2-cache"
            with patch("kabin.reader.fb2_cache_root", return_value=cache_root):
                first = open_reader_pages(fb2, "fb2")
                second = FB2Pages(fb2)
                self.assertEqual(second.toc, first.toc)
                self.assertEqual(second.page_bytes(0), first.page_bytes(0))

    def test_no_sections_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            fb2 = Path(tmp) / "empty.fb2"
            fb2.write_bytes(_FB2_EMPTY_BOOK)
            cache_root = Path(tmp) / "fb2-cache"
            with patch("kabin.reader.fb2_cache_root", return_value=cache_root):
                with self.assertRaises(ValueError):
                    open_reader_pages(fb2, "fb2")


class TestReaderProgress(unittest.TestCase):
    def test_resume_page_ignores_the_first_page_but_not_later_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            self.assertEqual(resume_page(config, "book:1"), 0)
            save_page_progress(config, "book:1", 0, 100)
            self.assertEqual(resume_page(config, "book:1"), 0)
            save_page_progress(config, "book:1", 42, 100)
            self.assertEqual(resume_page(config, "book:1"), 42)

    def test_resume_page_hides_once_finished(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            save_page_progress(config, "comic:1", 95, 100)
            self.assertEqual(resume_page(config, "comic:1"), 0)

    def test_txt_scroll_is_remembered_across_page_saves(self):
        # TXT is a single "page"; without scroll memory reopen always
        # tops out even after reading halfway down.
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            save_page_progress(config, "book:notes.txt", 0, 1, scroll=0.42)
            self.assertEqual(resume_scroll(config, "book:notes.txt"), 0.42)
            # Updating only the page index must not wipe mid-page place.
            save_page_progress(config, "book:notes.txt", 0, 1)
            self.assertEqual(resume_scroll(config, "book:notes.txt"), 0.42)
            save_page_progress(config, "book:notes.txt", 0, 1, scroll=0.0)
            self.assertEqual(resume_scroll(config, "book:notes.txt"), 0.0)

    def test_finished_book_clears_scroll_on_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            save_page_progress(config, "book:notes.txt", 1, 1, scroll=0.9)
            self.assertEqual(resume_scroll(config, "book:notes.txt"), 0.0)


def _local(item_id, media_type="comic", directory=None, contents=b"local book bytes"):
    """A local item backed by a real file, since sync compares file sizes."""
    extra = {}
    if directory is not None:
        path = Path(directory) / item_id.split(":", 1)[-1]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        extra["path"] = str(path)
    return SimpleNamespace(id=item_id, source="comic", media_type=media_type, extra=extra)


def _remote(remote_id, media_type="comic", progress=None, host="Office", size=None):
    return SimpleNamespace(
        id=f"remote:{host}:{remote_id}",
        source="remote",
        media_type=media_type,
        extra={
            "remote_id": remote_id,
            "progress": progress or {},
            "size": len(b"local book bytes") if size is None else size,
        },
    )


class TestSyncProgressFromRemote(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config = Config(path=Path(self._tmp.name) / "config.json")

    def test_adopts_remote_progress_onto_the_matching_local_item(self):
        games = [
            _local("comic:issue1.cbz", directory=self._tmp.name),
            _remote(
                "comic:issue1.cbz",
                progress={"position": 5, "duration": 20, "track": 0, "updated_at": 1000},
            ),
        ]
        sync_progress_from_remote(games, self.config)
        self.assertEqual(progress_for(self.config, "comic:issue1.cbz")["position"], 5)

    def test_local_progress_wins_when_it_is_newer(self):
        save_progress(self.config, "book:novel.epub", 40, 100)
        local_updated_at = progress_for(self.config, "book:novel.epub")["updated_at"]
        games = [
            _local("book:novel.epub", media_type="book", directory=self._tmp.name),
            _remote(
                "book:novel.epub",
                media_type="book",
                progress={
                    "position": 5,
                    "duration": 100,
                    "track": 0,
                    "updated_at": local_updated_at - 1000,
                },
            ),
        ]
        sync_progress_from_remote(games, self.config)
        self.assertEqual(progress_for(self.config, "book:novel.epub")["position"], 40)

    def test_no_matching_local_item_is_a_no_op(self):
        games = [
            _remote(
                "comic:unowned.cbz",
                progress={"position": 5, "duration": 20, "track": 0, "updated_at": 1000},
            ),
        ]
        sync_progress_from_remote(games, self.config)
        self.assertEqual(self.config.data.get("progress", {}), {})

    def test_a_different_book_with_the_same_name_does_not_contaminate(self):
        # Item ids are relative paths, so two differently-organised
        # libraries can share a filename ("01.cbz", "book.pdf") without
        # being the same book at all. Adopting on the id alone dropped the
        # reader onto a page of a book you never opened - and showed the
        # remote's page count in the progress ring.
        games = [
            _local("comic:01.cbz", directory=self._tmp.name, contents=b"a short local comic"),
            _remote(
                "comic:01.cbz",
                size=90210,  # a much bigger, unrelated book of the same name
                progress={"position": 300, "duration": 500, "track": 0, "updated_at": 9999},
            ),
        ]
        sync_progress_from_remote(games, self.config)
        self.assertEqual(self.config.data.get("progress", {}), {})

    def test_a_host_that_reports_no_size_is_skipped(self):
        games = [
            _local("comic:issue1.cbz", directory=self._tmp.name),
            _remote(
                "comic:issue1.cbz",
                size=0,
                progress={"position": 5, "duration": 20, "track": 0, "updated_at": 1000},
            ),
        ]
        sync_progress_from_remote(games, self.config)
        self.assertEqual(self.config.data.get("progress", {}), {})

    def test_remote_games_are_not_synced_as_reader_progress(self):
        games = [
            _local("roms:zelda.gba", media_type="game", directory=self._tmp.name),
            _remote(
                "roms:zelda.gba",
                media_type="game",
                progress={"position": 5, "duration": 20, "track": 0, "updated_at": 1000},
            ),
        ]
        sync_progress_from_remote(games, self.config)
        self.assertEqual(self.config.data.get("progress", {}), {})


class TestReaderWebViewPolicy(unittest.TestCase):
    def test_tap_zones_only_on_image_backends(self):
        self.assertTrue(uses_tap_zones("pdf"))
        self.assertTrue(uses_tap_zones("comic-zip"))
        self.assertFalse(uses_tap_zones("epub"))
        self.assertFalse(uses_tap_zones("fb2"))
        self.assertFalse(uses_tap_zones("text"))
        self.assertFalse(uses_tap_zones(None))

    def test_reader_uri_allows_only_in_book_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "book"
            root.mkdir()
            page = root / "OEBPS" / "chap1.xhtml"
            page.parent.mkdir()
            page.write_text("<p>hi</p>")
            outside = Path(tmp) / "secret.txt"
            outside.write_text("no")
            self.assertTrue(reader_uri_allowed("about:blank", [root]))
            self.assertTrue(reader_uri_allowed("data:text/html,hi", [root]))
            self.assertTrue(reader_uri_allowed(page.resolve().as_uri(), [root]))
            self.assertFalse(reader_uri_allowed(outside.resolve().as_uri(), [root]))
            self.assertFalse(reader_uri_allowed("https://example.com/track", [root]))
            self.assertFalse(reader_uri_allowed("javascript:alert(1)", [root]))
            self.assertFalse(reader_uri_allowed(page.resolve().as_uri(), []))

    def test_webview_settings_disable_script_and_file_access(self):
        calls = {}

        class Stub:
            def __getattr__(self, name):
                def setter(value, key=name):
                    calls[key] = value

                return setter

        apply_reader_webview_settings(Stub())
        self.assertFalse(calls["set_enable_javascript"])
        self.assertFalse(calls["set_allow_universal_access_from_file_urls"])
        self.assertFalse(calls["set_allow_file_access_from_file_urls"])

    def test_remote_read_cache_path_changes_with_size(self):
        first = remote_read_cache_path("host:1", "book:novel.epub", 10, ".epub")
        second = remote_read_cache_path("host:1", "book:novel.epub", 11, ".epub")
        self.assertNotEqual(first, second)
        self.assertTrue(str(first).endswith("item.epub"))
        item = SimpleNamespace(media_format="CBZ", extra={"remote_id": "comic:01.cbz"})
        self.assertEqual(remote_read_suffix(item), ".cbz")

    def test_step_adjustment_moves_within_bounds(self):
        class Adj:
            def __init__(self):
                self.value = 0
                self.lower = 0
                self.upper = 200
                self.page = 50

            def get_value(self):
                return self.value

            def get_lower(self):
                return self.lower

            def get_upper(self):
                return self.upper

            def get_page_size(self):
                return self.page

            def set_value(self, value):
                self.value = value

        adj = Adj()
        self.assertTrue(step_adjustment(adj, 1))
        self.assertGreater(adj.value, 0)
        adj.value = 150
        self.assertFalse(step_adjustment(adj, 1))
        self.assertEqual(adj.value, 150)
        self.assertTrue(step_adjustment(adj, -1))
        self.assertLess(adj.value, 150)
        self.assertFalse(step_adjustment(None, 1))


class TestRemoteReadCachePrune(unittest.TestCase):
    def test_prune_remote_read_cache_keeps_newest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "remote-read"
            with patch("kabin.reader.remote_read_cache_root", return_value=root):
                for i in range(5):
                    entry = root / f"book{i}"
                    entry.mkdir(parents=True)
                    (entry / "item.epub").write_bytes(b"x")
                    os.utime(entry, (i, i))
                prune_remote_read_cache(keep=2)
                left = sorted(p.name for p in root.iterdir())
                self.assertEqual(left, ["book3", "book4"])



if __name__ == "__main__":
    unittest.main()
