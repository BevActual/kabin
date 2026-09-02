from pathlib import Path


def safe_mtime(path: Path, default: float = 0.0) -> float:
    """path.stat().st_mtime, tolerating the file disappearing between
    being listed and being stat()'d - a real race for a library folder
    that's actively synced (e.g. by Syncthing) or on removable media,
    which would otherwise take the whole scan down with it."""
    try:
        return path.stat().st_mtime
    except OSError:
        return default
