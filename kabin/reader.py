from __future__ import annotations

from collections import OrderedDict

import base64
import hashlib
import html
import json
import os
import posixpath
import re
import shutil
import subprocess
import tarfile
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from . import playback
from .kinds import kind_for

READABLE_KINDS = frozenset({"book", "comic"})
IMAGE_READER_BACKENDS = frozenset(
    {"pdf", "comic-zip", "comic-tar", "comic-7z", "comic-rar"}
)
HTML_READER_BACKENDS = frozenset({"epub", "fb2"})
COMIC_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
_ALLOWED_READER_URI_SCHEMES = ("about:", "data:", "blob:")


def uses_tap_zones(backend: str | None) -> bool:
    """Left/right tap overlays belong on image pages, not scrollable text."""
    return backend in IMAGE_READER_BACKENDS


def _file_uri_path(uri: str) -> Path | None:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme.casefold() != "file":
        return None
    path = urllib.parse.unquote(parsed.path)
    return Path(path) if path else None


def reader_uri_allowed(uri: str, allowed_roots=None) -> bool:
    """Whether a WebView may load `uri` for a book page.

    Only in-book resources: about/data/blob, and file: under an extracted
    cache root. http(s), javascript:, and files outside the book are
    refused so an EPUB cannot phone home or read the rest of the disk.
    """
    if not uri:
        return False
    lowered = uri.strip().casefold()
    if lowered.startswith(_ALLOWED_READER_URI_SCHEMES):
        return True
    if not lowered.startswith("file:"):
        return False
    if not allowed_roots:
        return False
    path = _file_uri_path(uri)
    if path is None:
        return False
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in allowed_roots:
        try:
            if resolved.is_relative_to(Path(root).resolve()):
                return True
        except (OSError, ValueError):
            continue
    return False


def reader_cache_root(pages) -> Path | None:
    root = getattr(pages, "_root", None)
    return Path(root) if root else None


def apply_reader_webview_settings(settings) -> None:
    """Harden a WebKit.Settings object. Extracted so tests can pass a stub."""
    for name, value in (
        ("set_enable_javascript", False),
        ("set_enable_javascript_markup", False),
        ("set_allow_file_access_from_file_urls", False),
        ("set_allow_universal_access_from_file_urls", False),
        ("set_enable_developer_extras", False),
        ("set_enable_media", False),
        ("set_enable_webaudio", False),
        ("set_enable_webgl", False),
        ("set_enable_html5_database", False),
        ("set_enable_html5_local_storage", False),
        ("set_enable_offline_web_application_cache", False),
        ("set_enable_page_cache", False),
        ("set_enable_dns_prefetching", False),
    ):
        setter = getattr(settings, name, None)
        if callable(setter):
            setter(value)


def remote_read_cache_root() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "kabin" / "remote-read"


def remote_read_cache_path(host_key: str, remote_id: str, size: int, suffix: str) -> Path:
    identity = f"{host_key}\0{remote_id}\0{int(size or 0)}"
    digest = hashlib.sha256(identity.encode()).hexdigest()
    ext = suffix if suffix.startswith(".") else (f".{suffix}" if suffix else "")
    return remote_read_cache_root() / digest / f"item{ext}"


def remote_read_suffix(item) -> str:
    fmt = str(getattr(item, "media_format", "") or "").strip().lstrip(".")
    if fmt and fmt.casefold() != "album":
        return f".{fmt.casefold()}"
    remote_id = str((getattr(item, "extra", None) or {}).get("remote_id") or "")
    suffix = Path(remote_id.split(":")[-1]).suffix
    return suffix.casefold()


def scroll_adjustment(widget):
    """Find a vertical Gtk.Adjustment under `widget`, if any."""
    if widget is None:
        return None
    get_vadj = getattr(widget, "get_vadjustment", None)
    if callable(get_vadj):
        adj = get_vadj()
        if adj is not None:
            return adj
    get_first = getattr(widget, "get_first_child", None)
    if not callable(get_first):
        return None
    child = get_first()
    while child is not None:
        found = scroll_adjustment(child)
        if found is not None:
            return found
        child = child.get_next_sibling()
    return None


def step_adjustment(adj, direction: int, fraction: float = 0.85) -> bool:
    """Move a scroll adjustment by a page fraction. False if it could not move."""
    if adj is None or not direction:
        return False
    page = adj.get_page_size()
    step = page * fraction if page else 80
    lower = adj.get_lower()
    upper = adj.get_upper() - page
    current = adj.get_value()
    target = max(lower, min(upper, current + (step if direction > 0 else -step)))
    if target == current:
        return False
    adj.set_value(target)
    return True

_NATURAL_CHUNK = re.compile(r"(\d+)")


def _natural_sort_key(name: str) -> tuple:
    return tuple(
        int(part) if part.isdigit() else part.casefold()
        for part in _NATURAL_CHUNK.split(name)
    )


def _poppler_available() -> bool:
    try:
        import gi

        gi.require_version("Poppler", "0.18")
        from gi.repository import Poppler  # noqa: F401
    except (ImportError, ValueError):
        return False
    return True


def _webkit_available() -> bool:
    try:
        import gi

        gi.require_version("WebKit", "6.0")
        from gi.repository import WebKit  # noqa: F401
    except (ImportError, ValueError):
        return False
    return True


def _bsdtar_available() -> bool:
    return shutil.which("bsdtar") is not None


def reader_backend_for(item) -> str | None:
    """Which in-app backend (if any) can open this item, or None to fall
    back to the item's own `launch` (xdg-open)."""
    if kind_for(item).id not in READABLE_KINDS:
        return None
    path = playback.playable_file(item)
    if path is None:
        return None
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf" if _poppler_available() else None
    if suffix == ".cbz":
        return "comic-zip"
    if suffix == ".cbt":
        return "comic-tar"
    if suffix == ".cb7":
        return "comic-7z" if _bsdtar_available() else None
    if suffix == ".cbr":
        return "comic-rar" if _bsdtar_available() else None
    if suffix == ".epub":
        return "epub" if _webkit_available() else None
    if suffix == ".fb2":
        return "fb2" if _webkit_available() else None
    if suffix == ".txt":
        return "text"
    return None


def opens_in_kabin_reader(item) -> bool:
    return reader_backend_for(item) is not None


def _is_comic_image(name: str) -> bool:
    base = Path(name).name
    if not base or base.startswith("."):
        return False
    if "__MACOSX" in Path(name).parts:
        return False
    return Path(name).suffix.lower() in COMIC_IMAGE_SUFFIXES


class ComicZipPages:
    """On-demand page access into a CBZ (zip of images). No temp files —
    each page's bytes are read straight out of the archive."""

    def __init__(self, path: Path):
        self._archive = zipfile.ZipFile(path)
        self.names = sorted(
            (
                info.filename
                for info in self._archive.infolist()
                if not info.is_dir() and _is_comic_image(info.filename)
            ),
            key=_natural_sort_key,
        )

    def __len__(self) -> int:
        return len(self.names)

    def page_bytes(self, index: int) -> bytes:
        return self._archive.read(self.names[index])

    def close(self) -> None:
        self._archive.close()


class ComicTarPages:
    """On-demand page access into a CBT (tar of images)."""

    def __init__(self, path: Path):
        self._archive = tarfile.open(path)
        self._members = {
            member.name: member
            for member in self._archive.getmembers()
            if member.isfile() and _is_comic_image(member.name)
        }
        self.names = sorted(self._members, key=_natural_sort_key)

    def __len__(self) -> int:
        return len(self.names)

    def page_bytes(self, index: int) -> bytes:
        extracted = self._archive.extractfile(self._members[self.names[index]])
        if extracted is None:
            raise KeyError(self.names[index])
        return extracted.read()

    def close(self) -> None:
        self._archive.close()


def _bsdtar_list(path: Path) -> list[str]:
    result = subprocess.run(
        ["bsdtar", "-tf", str(path)],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return [line for line in result.stdout.splitlines() if line and not line.endswith("/")]


_BSDTAR_GLOB_CHARS = "*?[\\"


def _bsdtar_pattern(member: str) -> str:
    """Escape a member name so bsdtar matches it literally.

    bsdtar treats trailing arguments as shell-style *patterns*, not names,
    so a page called "page*.jpg" would otherwise match (and concatenate)
    every page in the archive - handing the reader one corrupt image built
    from several. Backslash-escaping the metacharacters makes it literal.
    """
    return "".join("\\" + ch if ch in _BSDTAR_GLOB_CHARS else ch for ch in member)


def _bsdtar_extract(path: Path, member: str) -> bytes:
    result = subprocess.run(
        ["bsdtar", "-xOf", str(path), _bsdtar_pattern(member)],
        capture_output=True,
        check=True,
        timeout=30,
    )
    return result.stdout



class _PageCache:
    """Tiny LRU for rendered/extracted reader pages.

    Comic archives shell out to bsdtar per page; PDFs re-rasterize through
    Poppler. Caching the last few keeps flipping back and forth from feeling
    like a cold open every time.
    """

    def __init__(self, limit: int = 5):
        self._limit = max(1, int(limit))
        self._items: OrderedDict = OrderedDict()

    def get(self, key):
        if key not in self._items:
            return None
        self._items.move_to_end(key)
        return self._items[key]

    def put(self, key, value):
        if key in self._items:
            self._items.move_to_end(key)
        self._items[key] = value
        while len(self._items) > self._limit:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()

class ComicArchivePages:
    """On-demand page access into any archive format `bsdtar` (libarchive)
    can read but Python's stdlib can't — CB7 (7z) and CBR (RAR). bsdtar
    auto-detects the format from content, so this same class covers both;
    listing happens once at open, and each page is extracted on demand."""

    def __init__(self, path: Path):
        self._path = path
        self.names = sorted(
            (name for name in _bsdtar_list(path) if _is_comic_image(name)),
            key=_natural_sort_key,
        )
        self._cache = _PageCache(5)

    def __len__(self) -> int:
        return len(self.names)

    def page_bytes(self, index: int, target_width: int | None = None) -> bytes:
        del target_width  # image archives are already pixels; width is a PDF concern
        cached = self._cache.get(index)
        if cached is not None:
            return cached
        data = _bsdtar_extract(self._path, self.names[index])
        self._cache.put(index, data)
        return data

    def close(self) -> None:
        self._cache.clear()


def open_comic_pages(path: Path, backend: str):
    if backend == "comic-zip":
        return ComicZipPages(path)
    if backend == "comic-tar":
        return ComicTarPages(path)
    if backend in ("comic-7z", "comic-rar"):
        return ComicArchivePages(path)
    raise ValueError(f"unsupported comic backend: {backend}")


class TextPages:
    """A plain-text book/comic as a single scrollable "page" — TXT has no
    natural pagination, so the whole file is one page and the reader UI
    lets the user scroll within it."""

    def __init__(self, path: Path):
        self._path = path

    def __len__(self) -> int:
        return 1

    def page_bytes(self, index: int) -> bytes:
        if index != 0:
            raise IndexError(index)
        return self._path.read_bytes()

    def close(self) -> None:
        pass


PDF_RENDER_WIDTH = 1600


class PdfPages:
    """Page access into a PDF, rendered on demand with Poppler/cairo.

    Exposes the same `len()`/`page_bytes(index)` shape as the comic-archive
    backends (PNG bytes here, source image bytes there) so the reader UI
    can treat every backend identically."""

    def __init__(self, path: Path):
        import gi

        gi.require_version("Poppler", "0.18")
        from gi.repository import Poppler

        self._document = Poppler.Document.new_from_file(path.resolve().as_uri())
        self._cache = _PageCache(4)

    def __len__(self) -> int:
        return self._document.get_n_pages()

    def page_bytes(self, index: int, target_width: int = PDF_RENDER_WIDTH) -> bytes:
        import io

        import cairo

        width = max(1, int(target_width or PDF_RENDER_WIDTH))
        cached = self._cache.get((index, width))
        if cached is not None:
            return cached

        page = self._document.get_page(index)
        page_width, page_height = page.get_size()
        scale = (width / page_width) if page_width else 1.0
        pixel_width = max(1, round(page_width * scale))
        pixel_height = max(1, round(page_height * scale))
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, pixel_width, pixel_height)
        ctx = cairo.Context(surface)
        ctx.set_source_rgb(1, 1, 1)
        ctx.paint()
        ctx.scale(scale, scale)
        page.render(ctx)
        surface.flush()
        buffer = io.BytesIO()
        surface.write_to_png(buffer)
        data = buffer.getvalue()
        self._cache.put((index, width), data)
        return data

    def close(self) -> None:
        self._cache.clear()
        self._document = None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


_XML_ELEMENT_START = re.compile(rb"<[A-Za-z_]")


def parse_xml(data: bytes):
    """ElementTree parse that refuses DTD-declared entities.

    ElementTree expands internal entities, so a book can nest them to blow
    up exponentially - a "billion laughs" bomb, where a few hundred bytes
    become gigabytes in memory. Ebooks routinely arrive from the internet,
    so refuse entity declarations rather than trusting the file. Only the
    prolog is scanned (declarations can't appear anywhere else), so content
    that merely mentions "<!ENTITY" still parses; the predefined XML
    entities and numeric character references are unaffected.
    """
    match = _XML_ELEMENT_START.search(data)
    prolog = data[: match.start()] if match else data
    if b"<!ENTITY" in prolog:
        raise ValueError("XML entity declarations are not allowed")
    return ET.fromstring(data)


def epub_cache_root() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "kabin" / "epub"


def cache_key_for(path: Path) -> str:
    """Cache directory name for `path`'s *current contents*.

    Keying on the path alone means replacing a book in place - a better
    scan re-downloaded over the old one, Calibre rewriting metadata,
    Syncthing pulling an update - keeps serving the previous extraction
    forever. Mixing in size and mtime makes a replaced file a cache miss
    without having to hash the whole book on every open.
    """
    try:
        info = path.stat()
        identity = f"{path.resolve()}\0{info.st_size}\0{info.st_mtime_ns}"
    except OSError:
        identity = str(path)
    return hashlib.sha256(identity.encode()).hexdigest()


# Each opened EPUB/FB2 is extracted to its own folder under the cache
# root. Nothing else prunes them, so without a cap the cache accumulates a
# second copy of every book ever opened - including books since deleted,
# and superseded copies of books edited in place.
CACHED_BOOKS_KEPT = 20


def touch_cache_dir(directory: Path) -> None:
    """Mark a cache folder as just-used, so pruning keeps it."""
    try:
        os.utime(directory)
    except OSError:
        pass


def prune_cache(root: Path, keep: int | None = None) -> None:
    """Keep only the `keep` most recently used extractions under `root`."""
    if keep is None:
        keep = CACHED_BOOKS_KEPT
    try:
        entries = [entry for entry in root.iterdir() if entry.is_dir()]
    except OSError:
        return

    def used_at(entry: Path) -> float:
        try:
            return entry.stat().st_mtime
        except OSError:
            return 0.0

    entries.sort(key=used_at, reverse=True)
    for stale in entries[keep:]:
        shutil.rmtree(stale, ignore_errors=True)


_EPUB_NAV_TYPE_ATTR = "{http://www.idpf.org/2007/ops}type"


def _resolve_toc_href(raw_href: str, doc_dir: str, hrefs: list[str]) -> int | None:
    """Map a TOC entry's href (nav/NCX-relative, may carry a #fragment) to
    a spine index, or None if it doesn't match any spine document."""
    if not raw_href:
        return None
    target = raw_href.split("#", 1)[0]
    if not target:
        return None
    normalized = posixpath.normpath(posixpath.join(doc_dir, urllib.parse.unquote(target)))
    try:
        return hrefs.index(normalized)
    except ValueError:
        return None


def _epub3_nav_toc(nav_root, nav_dir: str, hrefs: list[str]) -> list[dict]:
    navs = [el for el in nav_root.iter() if _local_name(el.tag) == "nav"]
    toc_nav = next((el for el in navs if el.get(_EPUB_NAV_TYPE_ATTR) == "toc"), None)
    toc_nav = toc_nav if toc_nav is not None else (navs[0] if navs else None)
    if toc_nav is None:
        return []
    entries = []
    for a in toc_nav.iter():
        if _local_name(a.tag) != "a" or not a.get("href"):
            continue
        index = _resolve_toc_href(a.get("href"), nav_dir, hrefs)
        if index is None:
            continue
        title = "".join(a.itertext()).strip()
        if title:
            entries.append({"title": title, "index": index})
    return entries


def _ncx_toc(ncx_root, ncx_dir: str, hrefs: list[str]) -> list[dict]:
    nav_map = next((el for el in ncx_root.iter() if _local_name(el.tag) == "navMap"), None)
    if nav_map is None:
        return []
    entries = []

    def walk(parent):
        for point in parent:
            if _local_name(point.tag) != "navPoint":
                continue
            label = next((c for c in point if _local_name(c.tag) == "navLabel"), None)
            content = next((c for c in point if _local_name(c.tag) == "content"), None)
            title = "".join(label.itertext()).strip() if label is not None else ""
            href = content.get("src") if content is not None else None
            if title and href:
                index = _resolve_toc_href(href, ncx_dir, hrefs)
                if index is not None:
                    entries.append({"title": title, "index": index})
            walk(point)

    walk(nav_map)
    return entries


def _extract_toc(archive, opf, items, manifest, opf_base_dir: str, hrefs: list[str]) -> list[dict]:
    """Best-effort table of contents: try the EPUB3 nav document first,
    then fall back to the EPUB2 NCX. Returns [] rather than raising if
    neither is present or parseable — a missing TOC never blocks reading."""
    nav_item = next(
        (item for item in items if "nav" in (item.get("properties") or "").split()),
        None,
    )
    if nav_item is not None and nav_item.get("href"):
        nav_path = posixpath.normpath(
            posixpath.join(opf_base_dir, urllib.parse.unquote(nav_item.get("href")))
        )
        try:
            nav_root = parse_xml(archive.read(nav_path))
            toc = _epub3_nav_toc(nav_root, posixpath.dirname(nav_path), hrefs)
            if toc:
                return toc
        except (KeyError, ET.ParseError):
            pass

    spine_el = next((el for el in opf.iter() if _local_name(el.tag) == "spine"), None)
    ncx_id = spine_el.get("toc") if spine_el is not None else None
    ncx_href = manifest.get(ncx_id) if ncx_id else None
    if not ncx_href:
        ncx_item = next(
            (item for item in items if (item.get("media-type") or "") == "application/x-dtbncx+xml"),
            None,
        )
        ncx_href = ncx_item.get("href") if ncx_item is not None else None
    if ncx_href:
        ncx_path = posixpath.normpath(
            posixpath.join(opf_base_dir, urllib.parse.unquote(ncx_href))
        )
        try:
            ncx_root = parse_xml(archive.read(ncx_path))
            return _ncx_toc(ncx_root, posixpath.dirname(ncx_path), hrefs)
        except (KeyError, ET.ParseError):
            pass
    return []


class EpubPages:
    """Chapter-level page access into an EPUB.

    Unlike the comic/PDF backends this doesn't rasterize pages — an EPUB is
    extracted once to a per-book cache folder (so relative image/CSS links
    resolve) and each "page" is one spine document's bytes, for a WebView to
    load directly. Page turning is therefore per spine document
    (chapter-ish), not per reflowed page. `self.toc` is a best-effort
    `[{"title": str, "index": int}, ...]` table of contents (from the
    EPUB3 nav doc or EPUB2 NCX, whichever is present) mapping each entry to
    a spine index — empty if the book has neither or neither parses."""

    def __init__(self, path: Path):
        digest = cache_key_for(path)
        cache_root = epub_cache_root()
        self._root = cache_root / digest
        spine_cache = self._root / ".kabin-spine.json"
        if spine_cache.is_file():
            try:
                cached = json.loads(spine_cache.read_text())
                self.hrefs = cached["hrefs"]
                self.toc = cached["toc"]
                touch_cache_dir(self._root)
                return
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                pass
        self.hrefs, self.toc = self._extract(path, spine_cache)
        touch_cache_dir(self._root)
        prune_cache(cache_root)

    def _extract(self, path: Path, spine_cache: Path) -> tuple[list[str], list[dict]]:
        with zipfile.ZipFile(path) as archive:
            container = parse_xml(archive.read("META-INF/container.xml"))
            rootfile = next(
                (
                    node
                    for node in container.iter()
                    if _local_name(node.tag) == "rootfile" and node.get("full-path")
                ),
                None,
            )
            if rootfile is None:
                raise ValueError("EPUB is missing a rootfile")
            opf_path = rootfile.get("full-path")
            opf = parse_xml(archive.read(opf_path))
            items = [item for item in opf.iter() if _local_name(item.tag) == "item"]
            manifest = {
                item.get("id"): item.get("href")
                for item in items
                if item.get("id") and item.get("href")
            }
            spine_ids = [
                item.get("idref")
                for item in opf.iter()
                if _local_name(item.tag) == "itemref" and item.get("idref") in manifest
            ]
            if not spine_ids:
                raise ValueError("EPUB has an empty spine")
            base_dir = posixpath.dirname(opf_path)
            hrefs = [
                posixpath.normpath(
                    posixpath.join(base_dir, urllib.parse.unquote(manifest[idref]))
                )
                for idref in spine_ids
            ]
            toc = _extract_toc(archive, opf, items, manifest, base_dir, hrefs)
            root = self._root.resolve()
            root.mkdir(parents=True, exist_ok=True)
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                target = (root / name).resolve()
                if root not in target.parents:
                    continue  # zip-slip guard: skip entries that escape the cache root
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
        spine_cache.write_text(json.dumps({"hrefs": hrefs, "toc": toc}))
        return hrefs, toc

    def __len__(self) -> int:
        return len(self.hrefs)

    def page_bytes(self, index: int) -> bytes:
        return (self._root / self.hrefs[index]).read_bytes()

    def page_base_uri(self, index: int) -> str:
        """Directory URI for `index`'s spine document, so a WebView can
        resolve its relative image/CSS links."""
        return (self._root / self.hrefs[index]).parent.resolve().as_uri() + "/"

    def close(self) -> None:
        pass


_FB2_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
_FB2_INLINE_TAGS = {
    "emphasis": "em",
    "strong": "strong",
    "strikethrough": "s",
    "sub": "sub",
    "sup": "sup",
    "code": "code",
}
_FB2_PAGE_STYLE = (
    "body{background:#15181f;color:#f4f1ea;font-family:serif;font-size:1.15em;"
    "line-height:1.6;padding:32px 48px;max-width:52em;margin:0 auto;}"
    "h2{font-weight:800;margin-top:0;}h3{font-weight:700;}"
    "img{max-width:100%;}blockquote{opacity:0.85;font-style:italic;}"
)


def _fb2_inline_html(elem) -> str:
    """Render one element's mixed text/child content (a <p>'s emphasis,
    line breaks, ...) as an inline HTML fragment."""
    parts = [html.escape(elem.text or "")]
    for child in elem:
        tag = _local_name(child.tag)
        if tag == "empty-line":
            parts.append("<br>")
        elif tag in _FB2_INLINE_TAGS:
            wrapper = _FB2_INLINE_TAGS[tag]
            parts.append(f"<{wrapper}>{_fb2_inline_html(child)}</{wrapper}>")
        else:
            parts.append(_fb2_inline_html(child))
        parts.append(html.escape(child.tail or ""))
    return "".join(parts)


def _fb2_block_html(elem, binaries: dict) -> str:
    """Render a <section>'s (or <epigraph>/<poem>/...) block-level content
    as an HTML fragment. Nested <section>s render inline rather than
    splitting into further pages — see FB2Pages."""
    out = []
    for child in elem:
        tag = _local_name(child.tag)
        if tag == "title":
            out.append(f"<h2>{_fb2_inline_html(child)}</h2>")
        elif tag == "subtitle":
            out.append(f"<h3>{_fb2_inline_html(child)}</h3>")
        elif tag == "p":
            out.append(f"<p>{_fb2_inline_html(child)}</p>")
        elif tag == "empty-line":
            out.append("<br>")
        elif tag in ("epigraph", "cite"):
            out.append(f"<blockquote>{_fb2_block_html(child, binaries)}</blockquote>")
        elif tag == "poem":
            out.append(f'<div class="poem">{_fb2_block_html(child, binaries)}</div>')
        elif tag == "stanza":
            lines = "".join(
                f"<div>{_fb2_inline_html(v)}</div>" for v in child if _local_name(v.tag) == "v"
            )
            out.append(f'<div class="stanza">{lines}</div>')
        elif tag == "image":
            href = (child.get(_FB2_XLINK_HREF) or child.get("href") or "").lstrip("#")
            name = binaries.get(href)
            if name:
                out.append(f'<img src="{name}">')
        elif tag == "section":
            out.append(_fb2_block_html(child, binaries))
        else:
            text = _fb2_inline_html(child).strip()
            if text:
                out.append(f"<p>{text}</p>")
    return "".join(out)


def fb2_cache_root() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "kabin" / "fb2"


class FB2Pages:
    """Page access into an FB2 book.

    FB2 is a single XML file (with embedded base64-encoded images), not an
    archive of documents like EPUB, so there's no natural "spine" — each
    "page" here is one top-level <body>/<section>, converted to a simple
    styled HTML fragment WebKit can render (matching EpubPages's
    `page_bytes`/`page_base_uri` shape so the reader UI treats both the
    same way). Footnote/annotation <body> elements (those with a `name`
    attribute) are skipped — only the main text is paginated. `self.toc`
    lists each page's title, same shape as EpubPages's, built for free
    from the section titles."""

    def __init__(self, path: Path):
        digest = cache_key_for(path)
        cache_root = fb2_cache_root()
        self._root = cache_root / digest
        cache_file = self._root / ".kabin-pages.json"
        if cache_file.is_file():
            try:
                cached = json.loads(cache_file.read_text())
                self._pages = cached["pages"]
                self.toc = cached["toc"]
                touch_cache_dir(self._root)
                return
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                pass
        self._pages, self.toc = self._extract(path, cache_file)
        touch_cache_dir(self._root)
        prune_cache(cache_root)

    def _extract(self, path: Path, cache_file: Path) -> tuple[list[str], list[dict]]:
        root = parse_xml(path.read_bytes())
        self._root.mkdir(parents=True, exist_ok=True)
        binaries = {}
        for binary in root:
            if _local_name(binary.tag) != "binary" or not binary.text:
                continue
            bid = binary.get("id")
            if not bid:
                continue
            try:
                data = base64.b64decode(binary.text, validate=False)
            except (ValueError, TypeError):
                continue
            if "." in bid:
                # FB2 binary ids are often already filename-shaped
                # ("cover.jpg") — don't double up the extension.
                name = bid
            else:
                content_type = binary.get("content-type", "")
                ext = ".png" if "png" in content_type else ".jpg"
                name = f"{bid}{ext}"
            (self._root / name).write_bytes(data)
            binaries[bid] = name

        bodies = [el for el in root if _local_name(el.tag) == "body"]
        main_bodies = [b for b in bodies if not b.get("name")] or bodies[:1]
        sections = [
            child
            for body in main_bodies
            for child in body
            if _local_name(child.tag) == "section"
        ]
        if not sections:
            raise ValueError("FB2 has no readable sections")

        pages = []
        toc = []
        for index, section in enumerate(sections):
            title_el = next((c for c in section if _local_name(c.tag) == "title"), None)
            title_text = re.sub("<[^>]+>", "", _fb2_inline_html(title_el)).strip() if title_el is not None else ""
            toc.append({"title": title_text or f"Section {index + 1}", "index": index})
            body_html = _fb2_block_html(section, binaries)
            pages.append(
                f'<html><head><meta charset="utf-8"><style>{_FB2_PAGE_STYLE}</style></head>'
                f"<body>{body_html}</body></html>"
            )
        cache_file.write_text(json.dumps({"pages": pages, "toc": toc}))
        return pages, toc

    def __len__(self) -> int:
        return len(self._pages)

    def page_bytes(self, index: int) -> bytes:
        return self._pages[index].encode("utf-8")

    def page_base_uri(self, index: int) -> str:
        return self._root.resolve().as_uri() + "/"

    def close(self) -> None:
        pass


def open_reader_pages(path: Path, backend: str):
    """Single entry point covering every backend. Every result exposes
    `len()`, `page_bytes(index) -> bytes`, and `close()`; the EPUB result
    additionally exposes `page_base_uri(index) -> str` (its spine
    document's directory, so relative image/CSS links resolve when a
    WebView loads it with `load_bytes(..., base_uri=...)`)."""
    if backend == "pdf":
        return PdfPages(path)
    if backend == "epub":
        return EpubPages(path)
    if backend == "fb2":
        return FB2Pages(path)
    if backend == "text":
        return TextPages(path)
    return open_comic_pages(path, backend)


def resume_page(config, item_id: str) -> int:
    """Like playback.resume_track, but pages don't get the seconds-based
    RESUME_AFTER gate — any saved page beyond the first counts."""
    info = playback.progress_for(config, item_id)
    position = info["position"]
    duration = info["duration"]
    if position <= 0:
        return 0
    if duration and position >= duration * playback.FINISHED_RATIO:
        return 0
    return int(position)


def save_page_progress(config, item_id: str, page: int, total: int) -> None:
    playback.save_progress(config, item_id, position=page, duration=total, track=0)


def sync_progress_from_remote(games, config) -> None:
    """Pull reading progress from paired Kabin hosts into matching local
    items, so resuming a book/comic follows you across devices — without
    needing to stream the file itself, the way video/music remote items
    do.

    Unlike video/music (which only ever exist as a "remote:<host>:<id>"
    ghost entry you stream through), a book/comic is something you'd
    typically keep a real local copy of on every device (synced via
    Syncthing or copied by hand). If a local item's id matches a remote
    catalog entry's own (unprefixed) id — same kind, same relative path
    under a media folder — and the two files are the same size, this
    adopts whichever side has read further, onto the *local* item's
    progress record (`playback.adopt_progress` already only overwrites
    when the incoming update is newer).

    The id is a relative path, so matching on it alone would let two
    differently-organised libraries that happen to share a filename
    ("01.cbz", "Chapter 1.epub") adopt each other's position. Comparing
    sizes as well keeps unrelated books apart; a host that doesn't publish
    a size is skipped rather than guessed at, since landing on the wrong
    page is worse than not syncing."""
    local_sizes = {
        game.id: _local_size(game) for game in games if game.source != "remote"
    }
    adopted = False
    for game in games:
        if game.source != "remote" or kind_for(game).id not in READABLE_KINDS:
            continue
        remote_id = game.extra.get("remote_id") or ""
        if remote_id not in local_sizes:
            continue
        remote_size = int(game.extra.get("size") or 0)
        if not remote_size or remote_size != local_sizes[remote_id]:
            continue
        if playback.adopt_progress(config, remote_id, game.extra.get("progress"), save=False):
            adopted = True
    if adopted:
        # One write for the whole refresh, rather than one per book.
        config.save()


def _local_size(item) -> int:
    path = playback.playable_file(item)
    if path is None:
        return 0
    try:
        return path.stat().st_size
    except OSError:
        return 0
