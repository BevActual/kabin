import json
import os
import time
from pathlib import Path

from .emulation import DEFAULT_EMULATION_SETTINGS

DEFAULT_CONFIG = {
    # each: {"path": str, "system": str, "extensions": [str], "emulator": "cmd {rom}"}
    "rom_dirs": [],
    "hidden": [],
    "sources": {"steam": True, "desktop": True, "roms": True},
    "steam_root": None,
    "recent": {},  # game id -> unix timestamp of last launch through kabin
    "favorites": [],
    "emulation": DEFAULT_EMULATION_SETTINGS,
    "artwork": {"steamgriddb_api_key": ""},
}


def _config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "kabin" / "config.json"


def _legacy_config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "omagames" / "config.json"


class Config:
    def __init__(self, path=None):
        self.path = Path(path) if path else _config_path()
        self._load_path = self.path
        if path is None and not self.path.exists() and _legacy_config_path().exists():
            self._load_path = _legacy_config_path()
        self.data = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
        loaded = self.load()
        if loaded and self._load_path != self.path:
            self.save()
            self._load_path = self.path

    def load(self):
        if self._load_path.exists():
            try:
                loaded = json.loads(self._load_path.read_text())
                self.data.update(loaded)
            except (json.JSONDecodeError, OSError):
                return False
            return True
        return False

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2))
        self.path.chmod(0o600)

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

    def add_rom_dir(self, path: str, system: str, extensions: list, emulator, bios_path=None):
        entry = {"path": path, "system": system, "extensions": extensions, "emulator": emulator}
        if bios_path:
            entry["bios_path"] = bios_path
        self.rom_dirs.append(entry)
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

    @property
    def emulation(self) -> dict:
        settings = self.data.setdefault("emulation", dict(DEFAULT_EMULATION_SETTINGS))
        for key, value in DEFAULT_EMULATION_SETTINGS.items():
            settings.setdefault(key, value)
        return settings

    @property
    def artwork(self) -> dict:
        return self.data.setdefault("artwork", {"steamgriddb_api_key": ""})

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
