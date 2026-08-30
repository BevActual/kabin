from . import desktop, remote, roms, steam


def discover_all_with_status(config) -> tuple[list, dict]:
    hidden = set(config.hidden)
    enabled = config.sources

    games = []
    steam_games = []
    if enabled.get("steam", True):
        steam_games = steam.get_games(config.data.get("steam_root"), hidden_ids=hidden)
        games.extend(steam_games)
    if enabled.get("desktop", True):
        steam_appids = {g.extra.get("appid") for g in steam_games}
        games.extend(
            desktop.get_games(
                hidden_ids=hidden,
                steam_appids=steam_appids,
                artwork_config=config.artwork,
            )
        )
    if enabled.get("roms", True):
        games.extend(
            roms.get_games(
                config.rom_dirs,
                hidden_ids=hidden,
                artwork_config=config.artwork,
                emulation_settings=config.emulation,
            )
        )
    host_statuses = {}
    if enabled.get("remote", True):
        remote_games, host_statuses = remote.discover(
            config.network.get("remote_hosts", []), hidden_ids=hidden
        )
        games.extend(remote_games)

    games.sort(key=lambda g: g.sort_key)
    return games, host_statuses


def discover_all(config) -> list:
    games, _host_statuses = discover_all_with_status(config)
    return games
