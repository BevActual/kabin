import json
import os
import time
from pathlib import Path

DEFAULT_CONFIG = {
    # each: {"path": str, "system": str, "extensions": [str], "emulator": "cmd {rom}"}
    "rom_dirs": [],
    "hidden": [],
    "sources": {"steam": True, "desktop": True, "roms": True},
    "steam_root": None,
    "recent": {},  # game id -> unix timestamp of last launch through omagames
    "favorites": [],
}


def _config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "omagames" / "config.json"


class Config:
    def __init__(self, path=None):
        self.path = Path(path) if path else _config_path()
        self.data = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
        self.load()

    def load(self):
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text())
                self.data.update(loaded)
            except (json.JSONDecodeError, OSError):
                pass
        return self.data

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2))

    @property
    def rom_dirs(self) -> list:
        return self.data.setdefault("rom_dirs", [])

    @property
    def hidden(self) -> list:
        return self.data.setdefault("hidden", [])

    @property
    def sources(self) -> dict:
        return self.data.setdefault("sources", dict(DEFAULT_CONFIG["sources"]))

    def is_hidden(self, game_id: str) -> bool:
        return game_id in self.hidden

    def hide(self, game_id: str):
        if game_id not in self.hidden:
            self.hidden.append(game_id)
            self.save()

    def unhide(self, game_id: str):
        if game_id in self.hidden:
            self.hidden.remove(game_id)
            self.save()

    def add_rom_dir(self, path: str, system: str, extensions: list, emulator: str):
        self.rom_dirs.append(
            {"path": path, "system": system, "extensions": extensions, "emulator": emulator}
        )
        self.save()

    def remove_rom_dir(self, index: int):
        if 0 <= index < len(self.rom_dirs):
            self.rom_dirs.pop(index)
            self.save()

    @property
    def recent(self) -> dict:
        return self.data.setdefault("recent", {})

    def record_played(self, game_id: str):
        self.recent[game_id] = time.time()
        self.save()

    def recent_ids(self, limit: int = 8) -> list:
        ordered = sorted(self.recent.items(), key=lambda kv: kv[1], reverse=True)
        return [game_id for game_id, _timestamp in ordered[:limit]]

    @property
    def favorites(self) -> list:
        return self.data.setdefault("favorites", [])

    def is_favorite(self, game_id: str) -> bool:
        return game_id in self.favorites

    def toggle_favorite(self, game_id: str) -> bool:
        """Flips favorite state for game_id and returns the new state."""
        if game_id in self.favorites:
            self.favorites.remove(game_id)
            is_favorite = False
        else:
            self.favorites.append(game_id)
            is_favorite = True
        self.save()
        return is_favorite
