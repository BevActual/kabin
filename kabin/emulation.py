from __future__ import annotations

import os
from pathlib import Path

from .systems import firmware_files


PRESETS = {
    "balanced": {
        "name": "Balanced",
        "description": "Smooth defaults with original scaling where practical.",
        "fullscreen": True,
        "vsync": True,
        "integer_scaling": False,
        "rewind": False,
    },
    "original": {
        "name": "Original Hardware",
        "description": "Integer-scaled pixels and conservative features.",
        "fullscreen": True,
        "vsync": True,
        "integer_scaling": True,
        "rewind": False,
    },
    "quality": {
        "name": "Quality",
        "description": "Presentation-focused defaults for modern displays.",
        "fullscreen": True,
        "vsync": True,
        "integer_scaling": False,
        "rewind": True,
    },
    "performance": {
        "name": "Performance",
        "description": "Reduced extras for slower hardware.",
        "fullscreen": True,
        "vsync": False,
        "integer_scaling": False,
        "rewind": False,
    },
}

DEFAULT_EMULATION_SETTINGS = {
    "preset": "balanced",
    "fullscreen": True,
    "vsync": True,
    "integer_scaling": False,
    "rewind": False,
}


def settings_for_preset(preset_id: str) -> dict:
    preset = PRESETS.get(preset_id, PRESETS["balanced"])
    return {
        key: value
        for key, value in preset.items()
        if key not in {"name", "description"}
    } | {"preset": preset_id if preset_id in PRESETS else "balanced"}


def connected_controllers(input_dir: Path = Path("/dev/input/by-id")) -> list[str]:
    try:
        devices = sorted(input_dir.glob("*-event-joystick"))
    except OSError:
        return []
    names = []
    for device in devices:
        name = device.name.removesuffix("-event-joystick")
        name = name.replace("usb-", "").replace("_", " ")
        if name not in names:
            names.append(name)
    return names


def system_readiness(system, entries: list[dict]) -> dict:
    """Return user-facing readiness for one console without mutating config."""
    entry = next((item for item in entries if item.get("system") == system.id), None)
    if entry is None:
        return {"ready": False, "state": "Not configured", "entry": None}

    path = Path(entry.get("path", "")).expanduser()
    if not path.is_dir():
        return {"ready": False, "state": "ROM folder is missing", "entry": entry}

    emulator = entry.get("emulator")
    if not emulator or (isinstance(emulator, dict) and not emulator.get("executable")):
        return {"ready": False, "state": "Emulator is missing", "entry": entry}
    if isinstance(emulator, dict) and emulator.get("runtime", "native") in {"native", "managed"}:
        executable = Path(emulator["executable"])
        if not executable.is_file() or not os.access(executable, os.X_OK):
            return {"ready": False, "state": "Emulator needs repair", "entry": entry}

    if system.firmware_required and not firmware_files(entry.get("bios_path")):
        return {"ready": False, "state": "BIOS is required", "entry": entry}

    return {"ready": True, "state": "Ready to play", "entry": entry}
