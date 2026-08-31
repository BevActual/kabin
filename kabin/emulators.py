from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .managed import installed_executable
from .systems import SystemDefinition, firmware_files


@dataclass(frozen=True)
class EmulatorChoice:
    id: str
    name: str
    runtime: str
    executable: str

    def to_config(self) -> dict:
        return {"id": self.id, "name": self.name, "runtime": self.runtime, "executable": self.executable}


_FLATPAK_IDS = {
    "dolphin": "org.DolphinEmu.dolphin-emu",
    "pcsx2": "net.pcsx2.PCSX2",
    "ppsspp": "org.ppsspp.PPSSPP",
}

_NATIVE_EMULATORS = {
    "nes": (("punes", "puNES", "punes"), ("mesen", "Mesen", "mesen")),
    "snes": (("snes9x", "Snes9x", "snes9x"), ("mesen", "Mesen", "mesen")),
    "n64": (("rmg", "RMG", "RMG"), ("mupen64plus", "Mupen64Plus", "mupen64plus")),
    "gb": (("mgba", "mGBA", "mgba-qt"), ("mgba", "mGBA", "mgba")),
    "gbc": (("mgba", "mGBA", "mgba-qt"), ("mgba", "mGBA", "mgba")),
    "gba": (("mgba", "mGBA", "mgba-qt"), ("mgba", "mGBA", "mgba")),
    "genesis": (("blastem", "BlastEm", "blastem"),),
    "ps1": (("duckstation", "DuckStation", "duckstation"), ("duckstation", "DuckStation", "duckstation-qt")),
    "ps2": (("pcsx2", "PCSX2", "pcsx2-qt"), ("pcsx2", "PCSX2", "pcsx2")),
    "psp": (("ppsspp", "PPSSPP", "PPSSPPSDL"), ("ppsspp", "PPSSPP", "ppsspp")),
    "gamecube": (("dolphin", "Dolphin", "dolphin-emu"), ("dolphin", "Dolphin", "dolphin")),
    "wii": (("dolphin", "Dolphin", "dolphin-emu"), ("dolphin", "Dolphin", "dolphin")),
    "arcade": (("mame", "MAME", "mame"),),
}

_SYSTEM_FLATPAK = {"ps2": "pcsx2", "psp": "ppsspp", "gamecube": "dolphin", "wii": "dolphin"}


def _flatpak_installed(app_id: str, home: Path | None = None) -> bool:
    home = home or Path.home()
    return any((root / app_id).exists() for root in (home / ".local/share/flatpak/app", Path("/var/lib/flatpak/app")))


def detect_emulators(system: SystemDefinition, home: Path | None = None) -> list[EmulatorChoice]:
    choices = []
    seen = set()
    for emulator_id, name, executable in _NATIVE_EMULATORS.get(system.id, ()):
        managed = installed_executable(emulator_id)
        if managed and emulator_id not in seen:
            choices.append(EmulatorChoice(emulator_id, f"{name} · Managed by Kabin", "managed", str(managed)))
            seen.add(emulator_id)
        resolved = shutil.which(executable)
        if resolved and emulator_id not in seen:
            choices.append(EmulatorChoice(emulator_id, name, "native", resolved))
            seen.add(emulator_id)

    flatpak_id = _SYSTEM_FLATPAK.get(system.id)
    if flatpak_id and flatpak_id not in seen:
        app_id = _FLATPAK_IDS[flatpak_id]
        if _flatpak_installed(app_id, home):
            choices.append(EmulatorChoice(flatpak_id, emulator_name(flatpak_id), "flatpak", app_id))
    return choices


def emulator_name(emulator_id: str) -> str:
    return {"dolphin": "Dolphin", "pcsx2": "PCSX2", "ppsspp": "PPSSPP"}.get(emulator_id, emulator_id.title())


def emulator_command(profile: dict) -> list[str]:
    runtime = profile.get("runtime", "native")
    executable = profile.get("executable", "")
    if not executable:
        raise ValueError("Emulator executable is missing")
    return [executable] if runtime in {"native", "managed"} else ["flatpak", "run", executable]


_BIOS_DATA_DIRS = {
    "duckstation": ("duckstation", "bios"),
    "pcsx2": ("PCSX2", "bios"),
}


def build_command(profile: dict, rom_path: Path, settings: dict | None = None) -> list[str]:
    command = emulator_command(profile)
    emulator_id = profile.get("id")
    options = settings or {}
    fullscreen = bool(options.get("fullscreen", False))
    vsync = bool(options.get("vsync", False))
    integer_scaling = bool(options.get("integer_scaling", False))
    if emulator_id == "dolphin":
        command.extend(["--batch", "--exec"])
        if fullscreen:
            command.append("--fullscreen")
    elif emulator_id == "duckstation":
        command.append("-batch")
        if fullscreen:
            command.append("-fullscreen")
    elif emulator_id == "pcsx2":
        command.append("-batch")
        if fullscreen:
            command.append("-fullscreen")
    elif emulator_id == "mame":
        if fullscreen:
            command.append("-nowindow")
        if vsync:
            command.append("-waitvsync")
        command.extend(["-rompath", str(rom_path.parent), rom_path.stem])
        return command
    elif fullscreen:
        fullscreen_flags = {
            "mgba": "-f",
            "snes9x": "-fullscreen",
            "mupen64plus": "--fullscreen",
            "blastem": "-f",
            "ppsspp": "--fullscreen",
            "punes": "--fullscreen",
        }
        flag = fullscreen_flags.get(emulator_id)
        if flag:
            command.append(flag)
    if emulator_id == "mupen64plus":
        if vsync:
            command.extend(["--set", "Video-General[VerticalSync]=True"])
        if integer_scaling:
            command.extend(["--set", "Video-General[IntegerScaling]=True"])
    command.append(str(rom_path))
    return command


def launch_environment(profile: dict, bios_path=None) -> dict | None:
    environment = None
    if profile.get("runtime") == "managed":
        root = Path(profile["executable"]).parent / "profile"
        directories = {
            "XDG_CONFIG_HOME": root / "config",
            "XDG_DATA_HOME": root / "data",
            "XDG_CACHE_HOME": root / "cache",
        }
        for directory in directories.values():
            directory.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment.update({key: str(value) for key, value in directories.items()})
    prepare_bios(profile, bios_path, environment)
    return environment


def prepare_bios(profile: dict, bios_path, environment: dict | None = None) -> None:
    """Link dumped firmware into the emulator's expected bios folder."""
    emulator_id = profile.get("id")
    layout = _BIOS_DATA_DIRS.get(emulator_id)
    if not bios_path or not layout:
        return
    files = firmware_files(bios_path)
    if not files:
        return
    if environment and environment.get("XDG_DATA_HOME"):
        data_home = Path(environment["XDG_DATA_HOME"])
    else:
        data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    destination = data_home.joinpath(*layout)
    destination.mkdir(parents=True, exist_ok=True)
    for source in files:
        target = destination / source.name
        if target.exists() or target.is_symlink():
            continue
        resolved = source.resolve()
        try:
            target.symlink_to(resolved)
        except OSError:
            shutil.copy2(resolved, target)
