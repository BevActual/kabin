from ..artwork import apply_chosen_covers
from ..kinds import FOLDER_KINDS
from . import desktop, media_dirs, remote, roms, steam


def discover_local_with_errors(config) -> tuple[list, dict[str, str]]:
    """Everything on this device: Steam, installed apps, ROMs, media folders.

    Returns (items, errors) where errors maps a source label to the
    exception that stopped it, so the window can say "Couldn't scan
    Steam" instead of a section silently going empty."""
    hidden = set(config.hidden)
    enabled = config.sources

    # Each source is isolated: one misbehaving source (an unreadable
    # Steam library, a malformed reply from a paired host, ...) shouldn't
    # keep every *other* source's titles from showing up. A refresh that
    # can't build a catalog at all is still caught one level up, in
    # window.py's refresh() - this is about graceful degradation, not the
    # last line of defense.
    games = []
    errors: dict[str, str] = {}
    steam_games = []
    if enabled.get("steam", True):
        try:
            steam_games = steam.get_games(config.data.get("steam_root"), hidden_ids=hidden)
        except Exception as exc:
            steam_games = []
            errors["Steam"] = _describe(exc)
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
        except Exception as exc:
            errors["Installed apps"] = _describe(exc)
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
        except Exception as exc:
            errors["Consoles"] = _describe(exc)
    folder_kinds = [kind.id for kind in FOLDER_KINDS if enabled.get(kind.id, True)]
    if folder_kinds:
        try:
            games.extend(
                media_dirs.get_items(
                    config.media_dirs,
                    hidden_ids=hidden,
                    enabled_kinds=folder_kinds,
                )
            )
        except Exception as exc:
            errors["Media folders"] = _describe(exc)

    apply_chosen_covers(games, config.covers)
    games.sort(key=lambda g: g.sort_key)
    return games, errors


def _describe(exc: Exception) -> str:
    text = str(exc).strip()
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def discover_local(config) -> list:
    games, _errors = discover_local_with_errors(config)
    return games


def remote_host_names(config) -> list[str]:
    """Paired hosts a refresh will ask, in the order they were paired."""
    if not config.sources.get("remote", True):
        return []
    return [
        host.get("name", "Kabin Host") for host in config.network.get("remote_hosts", [])
    ]


def discover_remote(config) -> tuple[list, dict]:
    """Catalogs from paired hosts. Slow when a host is off (connect
    timeout), so the window shows discover_local() first and merges this
    in when it lands."""
    if not remote_host_names(config):
        return [], {}
    try:
        games, host_statuses = remote.discover(
            config.network.get("remote_hosts", []), hidden_ids=set(config.hidden)
        )
    except Exception:
        return [], {}
    apply_chosen_covers(games, config.covers)
    games.sort(key=lambda g: g.sort_key)
    return games, host_statuses


def discover_all_with_status(config) -> tuple[list, dict]:
    games = discover_local(config)
    remote_games, host_statuses = discover_remote(config)
    games.extend(remote_games)
    games.sort(key=lambda g: g.sort_key)
    return games, host_statuses


def discover_all(config) -> list:
    games, _host_statuses = discover_all_with_status(config)
    return games
