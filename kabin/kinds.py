from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MediaKind:
    id: str
    label: str
    plural: str
    verb: str
    last_opened: str
    icon: str
    source: str
    shape: str
    tile_width: int
    tile_height: int
    details_width: int
    details_height: int
    min_columns: int
    max_columns: int
    extensions: frozenset[str]
    empty_hint: str
    accent: str = "#ffb454"


KINDS = {
    "game": MediaKind(
        id="game",
        label="Game",
        plural="Games",
        verb="Play",
        last_opened="Last played",
        icon="applications-games-symbolic",
        source="game",
        shape="portrait",
        tile_width=180,
        tile_height=240,
        details_width=320,
        details_height=430,
        min_columns=2,
        max_columns=12,
        extensions=frozenset(),
        empty_hint="Add a ROM folder in Settings, or install Steam games.",
        accent="#ffb454",
    ),
    "book": MediaKind(
        id="book",
        label="Book",
        plural="Books",
        verb="Read",
        last_opened="Last opened",
        icon="x-office-document-symbolic",
        source="book",
        shape="portrait",
        tile_width=168,
        tile_height=252,
        details_width=280,
        details_height=420,
        min_columns=2,
        max_columns=10,
        extensions=frozenset({".epub", ".pdf", ".mobi", ".azw3", ".fb2", ".txt"}),
        empty_hint="Add a Books folder in Settings. Kabin opens files with your default reader.",
        accent="#e8c99a",
    ),
    "comic": MediaKind(
        id="comic",
        label="Comic",
        plural="Comics",
        verb="Read",
        last_opened="Last opened",
        icon="x-office-document-symbolic",
        source="comic",
        shape="portrait",
        tile_width=176,
        tile_height=264,
        details_width=290,
        details_height=435,
        min_columns=2,
        max_columns=10,
        extensions=frozenset({".cbz", ".cbr", ".cb7", ".cbt"}),
        empty_hint="Add a Comics folder in Settings. CBZ and CBR files open in your reader.",
        accent="#ff8a6b",
    ),
    "music": MediaKind(
        id="music",
        label="Album",
        plural="Music",
        verb="Listen",
        last_opened="Last played",
        icon="audio-x-generic-symbolic",
        source="music",
        shape="square",
        tile_width=200,
        tile_height=200,
        details_width=360,
        details_height=360,
        min_columns=2,
        max_columns=8,
        extensions=frozenset({".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav", ".aac"}),
        empty_hint="Add a Music folder in Settings. Kabin plays albums here and remembers your place.",
        accent="#65d995",
    ),
    "video": MediaKind(
        id="video",
        label="Movie",
        plural="Movies",
        verb="Watch",
        last_opened="Last watched",
        icon="video-x-generic-symbolic",
        source="video",
        shape="landscape",
        tile_width=256,
        tile_height=144,
        details_width=480,
        details_height=270,
        min_columns=2,
        max_columns=6,
        extensions=frozenset({".mkv", ".mp4", ".avi", ".webm", ".mov", ".m4v"}),
        empty_hint="Add a Movies folder in Settings. Kabin plays films here and remembers your place.",
        accent="#7ec8e3",
    ),
}

CABINET_KIND = KINDS["game"]
FOLDER_KINDS = tuple(kind for kind in KINDS.values() if kind.extensions)


def get_kind(media_type: str | None) -> MediaKind:
    return KINDS.get(media_type or "game", CABINET_KIND)


def kind_for(item) -> MediaKind:
    return get_kind(getattr(item, "media_type", None))


def count_noun(count: int, kind: MediaKind) -> str:
    return kind.label.lower() if count == 1 else kind.plural.lower()
