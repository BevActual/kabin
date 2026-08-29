import os
import tomllib
from pathlib import Path

# Used when Omarchy's theme state can't be found (non-Omarchy machine, fresh
# install before a theme is set, etc.) — matches the "Matte Black" default.
FALLBACK_COLORS = {
    "accent": "#e68e0d",
    "background": "#121212",
    "dark_background": "#0d0d0d",
    "darker_background": "#090909",
    "lighter_background": "#1e1e1e",
    "foreground": "#bebebe",
    "dark_foreground": "#555555",
    "light_foreground": "#8a8a8d",
    "bright_foreground": "#bebebe",
    "selection": "#2a2a2a",
    "muted": "#333333",
}


def _theme_slug() -> str:
    path = Path.home() / ".local/state/omarchy/current/theme.name"
    try:
        slug = path.read_text().strip()
    except OSError:
        return ""
    return slug


def _theme_dir(slug: str) -> Path:
    user_dir = Path.home() / ".config/omarchy/themes" / slug
    if user_dir.is_dir():
        return user_dir
    base = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy"))
    return base / "themes" / slug


def load_colors() -> dict:
    """The active Omarchy theme's palette, falling back to defaults on any miss."""
    colors = dict(FALLBACK_COLORS)
    slug = _theme_slug()
    if not slug:
        return colors

    colors_path = _theme_dir(slug) / "colors.toml"
    try:
        with colors_path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return colors

    colors.update({k: v for k, v in data.items() if isinstance(v, str) and v.startswith("#")})
    return colors
