from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_TAG_PATTERN = re.compile(r"\s*[\[(][^\])]*[\])]\s*")
_YEAR = re.compile(r"^(?:19|20)\d{2}$")
_ISBN = re.compile(r"^isbn(?:13|10)?$", re.I)
_HASH = re.compile(r"^[0-9a-f]{16,}$", re.I)
_ARCHIVE = re.compile(r"anna.?s archive|libgen|z-library|zlib", re.I)
_VOLUME = re.compile(r"^(?P<series>.+?)[,_ ]+(?:vol\.?|volume)\s*(?P<index>\d+)\b(?P<rest>.*)$", re.I)
_TRACK_DASH = re.compile(r"\s-\s(\d{1,3})\s+")
_TRACK_PREFIX = re.compile(r"^(\d{1,3})[\s._-]+")
_ARTICLE_TAIL = re.compile(r"^(?P<body>.+),\s+(?P<article>The|A|An)$", re.I)
_VARIOUS_ARTISTS = re.compile(r"^Various Artists\b", re.I)


def _tidy(text: str) -> str:
    text = text.replace("_", " ")
    text = _TAG_PATTERN.sub(" ", text)
    return " ".join(text.split()).strip(" -–,")


def _is_junk(part: str) -> bool:
    token = part.strip()
    if not token:
        return True
    if _YEAR.match(token) or _ISBN.match(token.split()[0]) or _HASH.match(token):
        return True
    if token.lower().startswith("isbn"):
        return True
    if _ARCHIVE.search(token):
        return True
    return False


def restore_leading_article(name: str) -> str:
    if " - " in name:
        head, tail = name.split(" - ", 1)
        return f"{_flip_article(head)} - {tail}"
    return _flip_article(name)


def _flip_article(name: str) -> str:
    match = _ARTICLE_TAIL.match(name.strip())
    if not match:
        return name
    article = match.group("article")
    article = "The" if article.lower() == "the" else article.capitalize()
    return f"{article} {match.group('body')}"


def _pretty_creator(name: str) -> str:
    name = re.sub(r"^by\s+", "", _tidy(name), flags=re.I)
    parts = name.split()
    pretty = []
    index = 0
    while index < len(parts):
        token = parts[index].rstrip(".")
        if len(token) == 1 and token.isalpha():
            initials = [token.upper()]
            index += 1
            while index < len(parts) and len(parts[index].rstrip(".")) == 1 and parts[index].rstrip(".").isalpha():
                initials.append(parts[index].rstrip(".").upper())
                index += 1
            pretty.append(".".join(initials) + ".")
            continue
        pretty.append(parts[index])
        index += 1
    cleaned = " ".join(pretty).strip()
    if _VARIOUS_ARTISTS.match(cleaned):
        return "Various Artists"
    return restore_leading_article(cleaned)


@dataclass(frozen=True)
class ParsedName:
    title: str
    creators: tuple[str, ...] = ()
    series: str = ""
    series_index: float | None = None


def parse_media_name(name: str, media_type: str = "") -> ParsedName:
    raw = Path(name).stem if "." in Path(name).name else str(name)
    text = _tidy(raw)
    if not text:
        return ParsedName(title=raw or name)

    creators: list[str] = []
    series = ""
    series_index = None
    title = text

    if " -- " in text:
        head, *tail = [part.strip() for part in text.split(" -- ") if part.strip()]
        title = _tidy(head) or title
        leftovers = []
        for part in tail:
            if _is_junk(part):
                continue
            if _YEAR.match(part):
                continue
            if not creators:
                creators.append(_pretty_creator(part))
            else:
                leftovers.append(_tidy(part))
        if leftovers and not series:
            series = leftovers[0]

    elif media_type == "music" and " - " in text:
        artist, album = text.split(" - ", 1)
        if artist and album:
            title = _tidy(album) or title
            creators.append(_pretty_creator(artist))

    volume = _VOLUME.match(title)
    if volume:
        series = _tidy(volume.group("series")) or series
        series_index = float(volume.group("index"))
        rest = _tidy(volume.group("rest"))
        title = rest or f"{series} {int(series_index)}"

    return ParsedName(
        title=restore_leading_article(title or text),
        creators=tuple(name for name in creators if name),
        series=series,
        series_index=series_index,
    )


def embedded_track_number(name: str) -> int | None:
    filename = Path(name).name
    dashed = _TRACK_DASH.search(filename)
    if dashed:
        return int(dashed.group(1))
    prefixed = _TRACK_PREFIX.match(Path(filename).stem.replace("_", " ").strip())
    if prefixed:
        return int(prefixed.group(1))
    return None


def track_sort_key(path: Path) -> tuple:
    number = embedded_track_number(path.name)
    return (number if number is not None else 10_000, path.name.casefold())


def clean_track_title(name: str, album: str = "", artist: str = "") -> str:
    title = " ".join(Path(name).stem.replace("_", " ").split()).strip(" -")
    numbered = _TRACK_DASH.search(title)
    if numbered:
        after = title[numbered.end() :].strip(" -")
        if after:
            return after
    for prefix in filter(None, (artist, album)):
        needle = f"{prefix} - "
        if title.casefold().startswith(needle.casefold()):
            title = title[len(needle) :].strip(" -")
    title = _TRACK_PREFIX.sub("", title)
    return title.strip(" -") or Path(name).stem
