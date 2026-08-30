from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class LibraryItem:
    id: str
    title: str
    source: str
    subtitle: str = ""
    icon_path: Optional[str] = None
    icon_name: Optional[str] = None
    gicon: Optional[Any] = None
    launch: Optional[Callable[[], None]] = None
    extra: dict = field(default_factory=dict)
    media_type: str = "game"
    media_format: str = ""
    category: str = ""
    genres: list[str] = field(default_factory=list)
    creators: list[str] = field(default_factory=list)
    series: str = ""
    series_index: float | None = None

    @property
    def sort_key(self) -> str:
        return self.title.casefold()


# Compatibility name while game sources and emulator adapters migrate to the
# broader catalog terminology.
Game = LibraryItem
