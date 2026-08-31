import os
import shlex
import subprocess
from pathlib import Path

from ..artwork import clean_game_title, local_cover, resolve_local_cover
from ..emulators import build_command, launch_environment
from ..models import Game
from ..systems import get_system

_SKIP_DIRS = {"covers", "media", "images", "manuals", "videos", ".git"}


def _iter_rom_files(base: Path):
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name.casefold() not in _SKIP_DIRS and not name.startswith(".")
        )
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            path = Path(dirpath) / name
            if path.is_file() and not path.is_symlink():
                yield path


def _game_id(system_id: str, base: Path, rom_path: Path) -> str:
    try:
        relative = rom_path.relative_to(base)
    except ValueError:
        return f"roms:{system_id}:{rom_path.name}"
    if relative.parent == Path("."):
        return f"roms:{system_id}:{rom_path.name}"
    return f"roms:{system_id}:{relative.as_posix()}"


def custom_command(emulator: str, rom_path: Path) -> list[str]:
    """Split the template first so paths with spaces stay one argument."""
    return [part.replace("{rom}", str(rom_path)) for part in shlex.split(emulator)]


def get_games(
    rom_dirs_config,
    hidden_ids=None,
    artwork_config=None,
    emulation_settings=None,
) -> list:
    hidden_ids = hidden_ids or set()
    games = []
    for entry in rom_dirs_config:
        base = Path(entry.get("path", "")).expanduser()
        system_id = entry.get("system") or base.name or "ROMs"
        definition = get_system(system_id)
        system = definition.name if definition else system_id
        extensions = {e.lower().lstrip(".") for e in entry.get("extensions", []) if e}
        if definition:
            extensions.update(definition.extensions)
        emulator = entry.get("emulator", "")
        valid_emulator = isinstance(emulator, dict) or (
            isinstance(emulator, str) and "{rom}" in emulator
        )
        if not base.is_dir() or not valid_emulator:
            continue

        bios_path = entry.get("bios_path")
        for rom_path in _iter_rom_files(base):
            ext = rom_path.suffix.lower().lstrip(".")
            if extensions and ext not in extensions:
                continue

            gid = _game_id(system_id, base, rom_path)
            if gid in hidden_ids:
                continue

            title = clean_game_title(rom_path.name)
            cover = resolve_local_cover(gid, local_cover(rom_path))

            games.append(
                Game(
                    id=gid,
                    title=title,
                    source="roms",
                    subtitle=system,
                    icon_name="applications-games-symbolic",
                    icon_path=str(cover) if cover else None,
                    extra={
                        "path": str(rom_path),
                        "system": system_id,
                        "added_at": rom_path.stat().st_mtime,
                        "needs_artwork": cover is None,
                    },
                    launch=_make_launcher(emulator, rom_path, emulation_settings, bios_path),
                )
            )
    return games


def _make_launcher(emulator, rom_path: Path, emulation_settings=None, bios_path=None):
    def launch():
        if isinstance(emulator, dict):
            command = build_command(emulator, rom_path, emulation_settings)
            environment = launch_environment(emulator, bios_path)
        else:
            command = custom_command(emulator, rom_path)
            environment = None
        if environment is None:
            subprocess.Popen(command)
        else:
            subprocess.Popen(command, env=environment)

    return launch
