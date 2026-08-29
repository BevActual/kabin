from . import desktop, roms, steam


def discover_all(config) -> list:
    hidden = set(config.hidden)
    enabled = config.sources

    games = []
    steam_games = []
    if enabled.get("steam", True):
        steam_games = steam.get_games(config.data.get("steam_root"), hidden_ids=hidden)
        games.extend(steam_games)
    if enabled.get("desktop", True):
        steam_appids = {g.extra.get("appid") for g in steam_games}
        games.extend(desktop.get_games(hidden_ids=hidden, steam_appids=steam_appids))
    if enabled.get("roms", True):
        games.extend(roms.get_games(config.rom_dirs, hidden_ids=hidden))

    games.sort(key=lambda g: g.sort_key)
    return games
