from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class Game:
    id: str
    title: str
    source: str  # "steam" | "desktop" | "roms"
    subtitle: str = ""
    icon_path: Optional[str] = None
    icon_name: Optional[str] = None
    gicon: Optional[Any] = None  # Gio.Icon, for sources that expose one (e.g. desktop entries)
    launch: Optional[Callable[[], None]] = None
    extra: dict = field(default_factory=dict)

    @property
    def sort_key(self) -> str:
        return self.title.casefold()
