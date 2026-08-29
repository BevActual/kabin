from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SystemDefinition:
    id: str
    name: str
    extensions: tuple[str, ...]
    firmware_required: bool = False
    firmware_hint: str = ""


SYSTEMS = (
    SystemDefinition("nes", "Nintendo Entertainment System", ("nes", "fds", "zip")),
    SystemDefinition("snes", "Super Nintendo", ("sfc", "smc", "fig", "zip")),
    SystemDefinition("n64", "Nintendo 64", ("z64", "n64", "v64", "zip")),
    SystemDefinition("gb", "Game Boy", ("gb", "zip")),
    SystemDefinition("gbc", "Game Boy Color", ("gbc", "zip")),
    SystemDefinition("gba", "Game Boy Advance", ("gba", "zip")),
    SystemDefinition("genesis", "Sega Genesis / Mega Drive", ("md", "gen", "smd", "32x", "zip")),
    SystemDefinition(
        "ps1",
        "PlayStation",
        ("cue", "chd", "pbp", "iso"),
        True,
        "Choose a folder containing your dumped PlayStation BIOS.",
    ),
    SystemDefinition(
        "ps2",
        "PlayStation 2",
        ("iso", "chd", "cso"),
        True,
        "Choose a folder containing your dumped PlayStation 2 BIOS.",
    ),
    SystemDefinition("psp", "PlayStation Portable", ("iso", "cso", "pbp")),
    SystemDefinition("gamecube", "Nintendo GameCube", ("iso", "gcm", "rvz", "wia")),
    SystemDefinition("wii", "Nintendo Wii", ("iso", "wbfs", "rvz", "wia")),
    SystemDefinition("arcade", "Arcade", ("zip", "7z")),
)

SYSTEM_BY_ID = {system.id: system for system in SYSTEMS}


def get_system(system_id: str) -> SystemDefinition | None:
    return SYSTEM_BY_ID.get(system_id)


def firmware_files(path: str | Path | None) -> list[Path]:
    if not path:
        return []
    directory = Path(path).expanduser()
    if not directory.is_dir():
        return []
    return sorted(
        item
        for item in directory.iterdir()
        if item.is_file() and item.suffix.casefold() in {".bin", ".rom"}
    )
