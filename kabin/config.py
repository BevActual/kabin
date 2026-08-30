import json
import os
import secrets
import socket
import hashlib
import hmac
import time
from pathlib import Path

from .emulation import DEFAULT_EMULATION_SETTINGS

DEFAULT_CONFIG = {
    # each: {"path": str, "system": str, "extensions": [str], "emulator": "cmd {rom}"}
    "rom_dirs": [],
    "hidden": [],
    "hidden_titles": {},
    "sources": {"steam": True, "desktop": True, "roms": True, "remote": True},
    "steam_root": None,
    "recent": {},  # game id -> unix timestamp of last launch through kabin
    "favorites": [],
    "emulation": DEFAULT_EMULATION_SETTINGS,
    "artwork": {"steamgriddb_api_key": ""},
    "window": {"width": 1100, "height": 720, "maximized": False},
    "network": {
        "host_enabled": False,
        "host_name": "",
        "port": 42424,
        "token": "",
        "paired_devices": [],
        "remote_hosts": [],
    },
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
        sources = self.data.setdefault("sources", dict(DEFAULT_CONFIG["sources"]))
        for key, value in DEFAULT_CONFIG["sources"].items():
            sources.setdefault(key, value)
        return sources

    def is_hidden(self, game_id: str) -> bool:
        return game_id in self.hidden

    @property
    def hidden_titles(self) -> dict:
        return self.data.setdefault("hidden_titles", {})

    def hide(self, game_id: str, title: str | None = None):
        if game_id not in self.hidden:
            self.hidden.append(game_id)
        if title:
            self.hidden_titles[game_id] = title
        self.save()

    def unhide(self, game_id: str):
        if game_id in self.hidden:
            self.hidden.remove(game_id)
        self.hidden_titles.pop(game_id, None)
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

    @property
    def window(self) -> dict:
        settings = self.data.setdefault("window", dict(DEFAULT_CONFIG["window"]))
        for key, value in DEFAULT_CONFIG["window"].items():
            settings.setdefault(key, value)
        return settings

    def save_window_state(self, width: int, height: int, maximized: bool):
        if not maximized:
            self.window["width"] = max(640, int(width))
            self.window["height"] = max(480, int(height))
        self.window["maximized"] = bool(maximized)
        self.save()

    @property
    def network(self) -> dict:
        settings = self.data.setdefault("network", dict(DEFAULT_CONFIG["network"]))
        for key, value in DEFAULT_CONFIG["network"].items():
            settings.setdefault(key, value)
        if not settings["host_name"]:
            settings["host_name"] = socket.gethostname()
        return settings

    def ensure_network_token(self) -> str:
        if not self.network["token"]:
            self.network["token"] = secrets.token_urlsafe(32)
            self.save()
        return self.network["token"]

    def add_paired_device(self, name: str) -> str:
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        devices = self.network.setdefault("paired_devices", [])
        devices.append({"name": name, "token_hash": digest})
        self.save()
        return token

    def network_token_valid(self, token: str) -> bool:
        if not token:
            return False
        master = self.ensure_network_token()
        if hmac.compare_digest(token, master):
            return True
        digest = hashlib.sha256(token.encode()).hexdigest()
        return any(
            hmac.compare_digest(digest, device.get("token_hash", ""))
            for device in self.network.get("paired_devices", [])
        )

    def save_remote_host(self, host: dict, token: str):
        hosts = self.network.setdefault("remote_hosts", [])
        hosts[:] = [item for item in hosts if item.get("name") != host.get("name")]
        hosts.append(
            {
                "name": host["name"],
                "address": host["address"],
                "port": int(host["port"]),
                "token": token,
                "tls": bool(host.get("tls", False)),
                "fingerprint": host.get("fingerprint", ""),
            }
        )
        self.save()

    def remove_paired_device(self, index: int):
        devices = self.network.setdefault("paired_devices", [])
        if 0 <= index < len(devices):
            devices.pop(index)
            self.save()

    def remove_remote_host(self, name: str):
        hosts = self.network.setdefault("remote_hosts", [])
        hosts[:] = [host for host in hosts if host.get("name") != name]
        self.save()

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
