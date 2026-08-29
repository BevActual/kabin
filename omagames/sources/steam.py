import re
import subprocess
from pathlib import Path
from typing import Optional

from ..models import Game

_TOKEN_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])')

# Steam installs these as regular "apps" alongside real games. They have no
# store page and nothing to launch, so they'd otherwise show up as broken tiles.
_TOOL_NAME_RE = re.compile(
    r"^(Steamworks Common Redistributables|Proton\b.*|Steam Linux Runtime.*"
    r"|SteamVR.*|Steamworks.*)$",
    re.IGNORECASE,
)

_DEFAULT_ROOTS = [
    Path.home() / ".local/share/Steam",
    Path.home() / ".steam/steam",
    Path.home() / ".steam/root",
]


def parse_vdf(text: str) -> dict:
    """Minimal parser for Valve's text KeyValues (VDF) format."""
    tokens = []
    for m in _TOKEN_RE.finditer(text):
        tokens.append(m.group(2) if m.group(2) else m.group(1).replace('\\"', '"'))

    pos = 0

    def parse_object():
        nonlocal pos
        obj: dict = {}
        while pos < len(tokens):
            tok = tokens[pos]
            if tok == "}":
                pos += 1
                return obj
            key = tok
            pos += 1
            if pos < len(tokens) and tokens[pos] == "{":
                pos += 1
                obj[key] = parse_object()
            elif pos < len(tokens):
                obj[key] = tokens[pos]
                pos += 1
        return obj

    return parse_object()


def find_steam_root(override: Optional[str] = None) -> Optional[Path]:
    if override:
        p = Path(override).expanduser()
        if p.is_dir():
            return p
    for candidate in _DEFAULT_ROOTS:
        if (candidate / "steamapps").is_dir():
            return candidate
    return None


def library_paths(steam_root: Path) -> list:
    """All Steam library folders (the root itself, plus any added elsewhere)."""
    libraries = [steam_root]
    vdf_path = steam_root / "steamapps" / "libraryfolders.vdf"
    if not vdf_path.exists():
        return libraries
    try:
        data = parse_vdf(vdf_path.read_text(errors="replace"))
    except Exception:
        return libraries
    root = data.get("libraryfolders", data)
    for key, entry in root.items():
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if path:
            lib = Path(path)
            if lib not in libraries:
                libraries.append(lib)
    return libraries


def _is_real_game(name: str) -> bool:
    if not name:
        return False
    return not _TOOL_NAME_RE.match(name.strip())


def get_games(steam_root_override: Optional[str] = None, hidden_ids=None) -> list:
    hidden_ids = hidden_ids or set()
    steam_root = find_steam_root(steam_root_override)
    if steam_root is None:
        return []

    games = []
    seen_appids = set()
    for library in library_paths(steam_root):
        steamapps = library / "steamapps"
        if not steamapps.is_dir():
            continue
        for manifest in steamapps.glob("appmanifest_*.acf"):
            try:
                data = parse_vdf(manifest.read_text(errors="replace"))
            except Exception:
                continue
            state = data.get("AppState", {})
            appid = state.get("appid")
            name = state.get("name")
            if not appid or appid in seen_appids or not _is_real_game(name):
                continue
            seen_appids.add(appid)

            gid = f"steam:{appid}"
            if gid in hidden_ids:
                continue

            games.append(
                Game(
                    id=gid,
                    title=name,
                    source="steam",
                    subtitle="Steam",
                    extra={"appid": appid},
                    launch=_make_launcher(appid),
                )
            )
    return games


def _make_launcher(appid: str):
    def launch():
        subprocess.Popen(["steam", f"steam://rungameid/{appid}"])

    return launch
