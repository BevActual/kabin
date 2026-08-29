import shlex
import subprocess
from pathlib import Path

from ..models import Game


def get_games(rom_dirs_config, hidden_ids=None) -> list:
    hidden_ids = hidden_ids or set()
    games = []
    for entry in rom_dirs_config:
        base = Path(entry.get("path", "")).expanduser()
        system = entry.get("system") or base.name or "ROMs"
        extensions = {e.lower().lstrip(".") for e in entry.get("extensions", []) if e}
        emulator_template = entry.get("emulator", "")
        if not base.is_dir() or not emulator_template or "{rom}" not in emulator_template:
            continue

        for rom_path in sorted(base.iterdir()):
            if not rom_path.is_file():
                continue
            ext = rom_path.suffix.lower().lstrip(".")
            if extensions and ext not in extensions:
                continue

            gid = f"roms:{system}:{rom_path.name}"
            if gid in hidden_ids:
                continue

            games.append(
                Game(
                    id=gid,
                    title=rom_path.stem,
                    source="roms",
                    subtitle=system,
                    icon_name="applications-games-symbolic",
                    extra={"path": str(rom_path), "system": system},
                    launch=_make_launcher(emulator_template, rom_path),
                )
            )
    return games


def _make_launcher(emulator_template: str, rom_path: Path):
    def launch():
        command = emulator_template.replace("{rom}", str(rom_path))
        subprocess.Popen(shlex.split(command))

    return launch
