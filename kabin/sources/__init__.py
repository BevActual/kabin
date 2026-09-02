from ..artwork import apply_chosen_covers
from . import desktop, media_dirs, remote, roms, steam


def discover_all_with_status(config) -> tuple[list, dict]:
    hidden = set(config.hidden)
    enabled = config.sources

    # Each source is isolated: one misbehaving source (an unreadable
    # Steam library, a malformed reply from a paired host, ...) shouldn't
    # keep every *other* source's titles from showing up. A refresh that
    # can't build a catalog at all is still caught one level up, in
    # window.py's refresh() - this is about graceful degradation, not the
    # last line of defense.
    games = []
    steam_games = []
    if enabled.get("steam", True):
        try:
            steam_games = steam.get_games(config.data.get("steam_root"), hidden_ids=hidden)
        except Exception:
            steam_games = []
        games.extend(steam_games)
    if enabled.get("desktop", True):
        steam_appids = {g.extra.get("appid") for g in steam_games}
        try:
            games.extend(
                desktop.get_games(
                    hidden_ids=hidden,
                    steam_appids=steam_appids,
                    artwork_config=config.artwork,
                )
            )
        except Exception:
            pass
    if enabled.get("roms", True):
        try:
            games.extend(
                roms.get_games(
                    config.rom_dirs,
                    hidden_ids=hidden,
                    artwork_config=config.artwork,
                    emulation_settings=config.emulation,
                )
            )
        except Exception:
            pass
    host_statuses = {}
    if enabled.get("remote", True):
        try:
            remote_games, host_statuses = remote.discover(
                config.network.get("remote_hosts", []), hidden_ids=hidden
            )
            games.extend(remote_games)
        except Exception:
            pass
    folder_kinds = [
        kind
        for kind in ("book", "comic", "music", "video")
        if enabled.get(kind, True)
    ]
    if folder_kinds:
        try:
            games.extend(
                media_dirs.get_items(
                    config.media_dirs,
                    hidden_ids=hidden,
                    enabled_kinds=folder_kinds,
                )
            )
        except Exception:
            pass

    apply_chosen_covers(games, config.covers)
    games.sort(key=lambda g: g.sort_key)
    return games, host_statuses


def discover_all(config) -> list:
    games, _host_statuses = discover_all_with_status(config)
    return games
