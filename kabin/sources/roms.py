import shlex
import subprocess
from pathlib import Path

from ..artwork import clean_game_title, local_cover, resolve_cover
from ..emulators import build_command, launch_environment
from ..models import Game
from ..systems import get_system


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

        for rom_path in sorted(base.iterdir()):
            if not rom_path.is_file():
                continue
            ext = rom_path.suffix.lower().lstrip(".")
            if extensions and ext not in extensions:
                continue

            gid = f"roms:{system_id}:{rom_path.name}"
            if gid in hidden_ids:
                continue

            title = clean_game_title(rom_path.name)
            cover = resolve_cover(title, gid, artwork_config, local_cover(rom_path))

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
                    },
                    launch=_make_launcher(emulator, rom_path, emulation_settings),
                )
            )
    return games


def _make_launcher(emulator, rom_path: Path, emulation_settings=None):
    def launch():
        if isinstance(emulator, dict):
            command = build_command(emulator, rom_path, emulation_settings)
            environment = launch_environment(emulator)
        else:
            command = shlex.split(emulator.replace("{rom}", str(rom_path)))
            environment = None
        if environment is None:
            subprocess.Popen(command)
        else:
            subprocess.Popen(command, env=environment)

    return launch
