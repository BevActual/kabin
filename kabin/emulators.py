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
    "nes": (
        ("fceux", "FCEUX", "fceux"),
        ("punes", "puNES", "punes"),
        ("mesen", "Mesen", "mesen"),
    ),
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


def _flag01(value: bool) -> str:
    return "1" if value else "0"


def _with_rom(command: list[str], rom_path: Path) -> list[str]:
    command.append(str(rom_path))
    return command


def _adapt_fceux(command, rom_path, fullscreen, vsync, integer_scaling, rewind):
    # 2.6 Qt/SDL takes 0|1 values. VSync and rewind are config-file only.
    del vsync, rewind
    command.extend(["--fullscreen", _flag01(fullscreen)])
    if integer_scaling:
        command.extend(["--autoscale", "0", "--xstretch", "0", "--ystretch", "0"])
    else:
        command.extend(["--autoscale", "1", "--keepratio", "1"])
    return _with_rom(command, rom_path)


def _adapt_mgba(command, rom_path, fullscreen, vsync, integer_scaling, rewind):
    if fullscreen:
        command.append("-f")
    command.extend(["-C", f"videoSync={_flag01(vsync)}"])
    command.extend(["-C", f"rewindEnable={_flag01(rewind)}"])
    command.extend(["-C", "lockAspectRatio=1"])
    command.extend(["-C", f"lockIntegerScaling={_flag01(integer_scaling)}"])
    return _with_rom(command, rom_path)


def _adapt_snes9x(command, rom_path, fullscreen, vsync, integer_scaling, rewind):
    del vsync
    if fullscreen:
        command.append("-fullscreen")
    if not integer_scaling:
        command.append("-maxaspect")
    command.extend(["-rwbuffersize", "16" if rewind else "0"])
    return _with_rom(command, rom_path)


def _adapt_mupen64plus(command, rom_path, fullscreen, vsync, integer_scaling, rewind):
    # Integer scaling is plugin-specific; do not invent a Video-General key.
    del integer_scaling, rewind
    command.append("--fullscreen" if fullscreen else "--windowed")
    command.extend(["--set", f"Video-General[VerticalSync]={vsync}"])
    command.append("--nosaveoptions")
    return _with_rom(command, rom_path)


def _adapt_mame(command, rom_path, fullscreen, vsync, integer_scaling, rewind):
    command.append("-nowindow" if fullscreen else "-window")
    command.append("-waitvsync" if vsync else "-nowaitvsync")
    if integer_scaling:
        command.extend(["-intscalex", "1", "-intscaley", "1"])
    command.append("-rewind" if rewind else "-norewind")
    command.extend(["-rompath", str(rom_path.parent), rom_path.stem])
    return command


def _adapt_dolphin(command, rom_path, fullscreen, vsync, integer_scaling, rewind):
    del integer_scaling, rewind
    command.extend(["--batch", "--exec"])
    command.append(f"--config=Dolphin.Display.Fullscreen={'True' if fullscreen else 'False'}")
    command.append(f"--config=GFX.Hardware.VSync={'True' if vsync else 'False'}")
    return _with_rom(command, rom_path)


def _adapt_duckstation(command, rom_path, fullscreen, vsync, integer_scaling, rewind):
    del vsync, integer_scaling, rewind
    command.append("-batch")
    if fullscreen:
        command.append("-fullscreen")
    return _with_rom(command, rom_path)


def _adapt_pcsx2(command, rom_path, fullscreen, vsync, integer_scaling, rewind):
    del vsync, integer_scaling, rewind
    command.append("-batch")
    if fullscreen:
        command.append("-fullscreen")
    return _with_rom(command, rom_path)


def _adapt_ppsspp(command, rom_path, fullscreen, vsync, integer_scaling, rewind):
    del vsync, integer_scaling, rewind
    command.append("--fullscreen" if fullscreen else "--windowed")
    return _with_rom(command, rom_path)


_FULLSCREEN_FLAGS = {
    "blastem": "-f",
    "punes": "--fullscreen",
    "mesen": "--fullscreen",
}

_ADAPTERS = {
    "fceux": _adapt_fceux,
    "mgba": _adapt_mgba,
    "snes9x": _adapt_snes9x,
    "mupen64plus": _adapt_mupen64plus,
    "mame": _adapt_mame,
    "dolphin": _adapt_dolphin,
    "duckstation": _adapt_duckstation,
    "pcsx2": _adapt_pcsx2,
    "ppsspp": _adapt_ppsspp,
}


def build_command(profile: dict, rom_path: Path, settings: dict | None = None) -> list[str]:
    """Translate Kabin's play profile into one emulator's argv.

    Unknown or unsupported switches are omitted rather than guessed — a
    flag the binary does not have would abort the launch. When `settings`
    is omitted, only the flags required to start the game are added.
    """
    command = emulator_command(profile)
    emulator_id = profile.get("id")
    options = settings or {}
    fullscreen = bool(options.get("fullscreen", False))
    vsync = bool(options.get("vsync", False))
    integer_scaling = bool(options.get("integer_scaling", False))
    rewind = bool(options.get("rewind", False))
    adapter = _ADAPTERS.get(emulator_id)
    if adapter and settings is not None:
        return adapter(command, rom_path, fullscreen, vsync, integer_scaling, rewind)
    if emulator_id == "dolphin":
        command.extend(["--batch", "--exec"])
    elif emulator_id in {"duckstation", "pcsx2"}:
        command.append("-batch")
    elif emulator_id == "mame":
        command.extend(["-rompath", str(rom_path.parent), rom_path.stem])
        return command
    if fullscreen:
        flag = _FULLSCREEN_FLAGS.get(emulator_id)
        if flag:
            command.append(flag)
    return _with_rom(command, rom_path)


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
        if target.exists():
            continue
        if target.is_symlink():
            # A dangling symlink (its target moved or was renamed, e.g.
            # after repointing the BIOS folder in Settings) - exists() is
            # False for these even though is_symlink() is True, so without
            # this it would never get repaired.
            target.unlink()
        resolved = source.resolve()
        try:
            target.symlink_to(resolved)
        except OSError:
            shutil.copy2(resolved, target)
