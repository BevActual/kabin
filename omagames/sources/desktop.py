import re

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio  # noqa: E402

from ..models import Game  # noqa: E402

# Steam owns its own launch path via sources/steam.py; skip its launcher entry
# and omagames' own launcher entry (Categories=Game, since it's a game
# launcher, would otherwise list itself) so they don't show up as "games".
_EXCLUDED_IDS = {"steam.desktop", "omagames.desktop"}

_STEAM_RUNGAME_RE = re.compile(r"steam://rungameid/(\d+)")


def get_games(hidden_ids=None, steam_appids=None) -> list:
    """Scans installed .desktop entries categorized as games.

    `steam_appids` lets callers skip desktop shortcuts that just wrap
    `steam steam://rungameid/<id>` for a game the Steam source already
    found, since that's the same game launched the same way twice.
    """
    hidden_ids = hidden_ids or set()
    steam_appids = steam_appids or set()
    games = []
    for app_info in Gio.AppInfo.get_all():
        if not isinstance(app_info, Gio.DesktopAppInfo):
            continue
        desktop_id = app_info.get_id() or ""
        if desktop_id in _EXCLUDED_IDS:
            continue
        if app_info.get_nodisplay() or not app_info.should_show():
            continue

        categories = (app_info.get_string("Categories") or "").split(";")
        if "Game" not in categories:
            continue

        exec_line = app_info.get_string("Exec") or ""
        rungame_match = _STEAM_RUNGAME_RE.search(exec_line)
        if rungame_match and rungame_match.group(1) in steam_appids:
            continue

        gid = f"desktop:{desktop_id}"
        if gid in hidden_ids:
            continue

        title = app_info.get_display_name() or app_info.get_name() or desktop_id

        games.append(
            Game(
                id=gid,
                title=title,
                source="desktop",
                subtitle="",
                gicon=app_info.get_icon(),
                launch=_make_launcher(app_info),
            )
        )
    return games


def _make_launcher(app_info: "Gio.DesktopAppInfo"):
    def launch():
        app_info.launch([], None)

    return launch
