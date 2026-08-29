from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path


class ManagedRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeSpec:
    id: str
    name: str
    repository: str
    systems: tuple[str, ...]
    asset_patterns: dict[str, str]


RUNTIMES = (
    RuntimeSpec(
        "duckstation",
        "DuckStation",
        "stenzek/duckstation",
        ("ps1",),
        {
            "x86_64": r"DuckStation-x64\.AppImage$",
            "aarch64": r"arm64.*\.AppImage$",
        },
    ),
    RuntimeSpec(
        "pcsx2",
        "PCSX2",
        "PCSX2/pcsx2",
        ("ps2",),
        {
            "x86_64": r"(?:x64|x86_64).*\.AppImage$",
            "aarch64": r"(?:arm64|aarch64).*\.AppImage$",
        },
    ),
    RuntimeSpec(
        "ppsspp",
        "PPSSPP",
        "hrydgard/ppsspp",
        ("psp",),
        {
            "x86_64": r"anylinux-x86_64\.AppImage$",
            "aarch64": r"anylinux-aarch64\.AppImage$",
        },
    ),
)

RUNTIME_BY_ID = {runtime.id: runtime for runtime in RUNTIMES}


def runtime_root() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "kabin" / "emulators"


def architecture() -> str:
    machine = platform.machine().casefold()
    return {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)


def recommended_runtime(system_id: str) -> RuntimeSpec | None:
    return next((runtime for runtime in RUNTIMES if system_id in runtime.systems), None)


def installed_executable(runtime_id: str, root: Path | None = None) -> Path | None:
    executable = (root or runtime_root()) / runtime_id / runtime_id
    return executable if executable.is_file() and os.access(executable, os.X_OK) else None


def _request_json(url: str, opener=urllib.request.urlopen) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Kabin/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with opener(request, timeout=15) as response:
        return json.loads(response.read())


def resolve_asset(spec: RuntimeSpec, opener=urllib.request.urlopen) -> dict:
    arch = architecture()
    pattern = spec.asset_patterns.get(arch)
    if not pattern:
        raise ManagedRuntimeError(f"{spec.name} has no managed build for {arch}")
    release = _request_json(
        f"https://api.github.com/repos/{spec.repository}/releases/latest",
        opener,
    )
    asset = next(
        (item for item in release.get("assets", []) if re.search(pattern, item.get("name", ""), re.I)),
        None,
    )
    if not asset:
        raise ManagedRuntimeError(f"No compatible {spec.name} release asset was found")
    digest = asset.get("digest") or ""
    if not digest.startswith("sha256:"):
        raise ManagedRuntimeError(f"{spec.name} did not publish a verifiable SHA-256 digest")
    return {
        "name": asset["name"],
        "url": asset["browser_download_url"],
        "sha256": digest.removeprefix("sha256:"),
        "version": release.get("tag_name", "unknown"),
    }


def install_runtime(
    spec: RuntimeSpec,
    root: Path | None = None,
    opener=urllib.request.urlopen,
) -> Path:
    asset = resolve_asset(spec, opener)
    directory = (root or runtime_root()) / spec.id
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / spec.id
    temporary = directory / f".{spec.id}.download"
    request = urllib.request.Request(asset["url"], headers={"User-Agent": "Kabin/0.1"})
    digest = hashlib.sha256()
    try:
        with opener(request, timeout=60) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest() != asset["sha256"]:
            raise ManagedRuntimeError(f"{spec.name} download failed checksum verification")
        temporary.chmod(0o755)
        temporary.replace(destination)
        metadata = {key: asset[key] for key in ("name", "url", "sha256", "version")}
        (directory / "runtime.json").write_text(json.dumps(metadata, indent=2) + "\n")
        return destination
    finally:
        temporary.unlink(missing_ok=True)
