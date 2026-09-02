from __future__ import annotations

import ssl
import urllib.error
from concurrent.futures import ThreadPoolExecutor

from ..kinds import get_kind
from ..models import Game
from ..network import fetch_remote_library


def discover(
    hosts: list[dict],
    hidden_ids=None,
    fetcher=None,
) -> tuple[list[Game], dict[str, dict]]:
    """Fetch every paired host's catalog.

    Hosts are queried concurrently: an unreachable host costs a full
    connect timeout, and querying them one at a time made that cost add
    up per powered-off device on every refresh."""
    hidden_ids = hidden_ids or set()
    fetcher = fetcher or fetch_remote_library
    if not hosts:
        return [], {}
    with ThreadPoolExecutor(max_workers=min(len(hosts), 8)) as pool:
        results = list(pool.map(lambda host: _fetch_host(host, hidden_ids, fetcher), hosts))
    games = []
    statuses = {}
    for name, status, host_games in results:
        statuses[name] = status
        games.extend(host_games)
    return games, statuses


def _fetch_host(host: dict, hidden_ids, fetcher) -> tuple[str, dict, list[Game]]:
    name = host.get("name", "Kabin Host")
    token = host.get("token")
    if not token:
        return name, {"state": "auth", "message": "Pairing required"}, []
    try:
        payload = fetcher(host, token)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            status = {"state": "auth", "message": "Re-pair required"}
        else:
            status = {"state": "offline", "message": f"HTTP {exc.code}"}
        exc.close()
        return name, status, []
    except ssl.SSLError:
        return name, {"state": "auth", "message": "Host identity changed"}, []
    except (OSError, TimeoutError) as exc:
        return name, {"state": "offline", "message": str(exc) or "Unavailable"}, []
    except Exception as exc:
        return name, {"state": "offline", "message": str(exc) or "Unavailable"}, []
    return name, {"state": "online", "message": "Online"}, _games_from_payload(host, name, payload, hidden_ids)


def _games_from_payload(host: dict, name: str, payload: dict, hidden_ids) -> list[Game]:
    games = []
    for remote in payload.get("items", payload.get("games", [])):
        remote_id = str(remote.get("id", ""))
        title = str(remote.get("title", "")).strip()
        if not remote_id or not title:
            continue
        game_id = f"remote:{name}:{remote_id}"
        if game_id in hidden_ids:
            continue
        kind = get_kind(remote.get("media_type", "game"))
        games.append(
            Game(
                id=game_id,
                title=title,
                source="remote",
                subtitle=name,
                icon_name=kind.icon,
                extra={
                    "host": dict(host),
                    "remote_id": remote_id,
                    "remote_source": remote.get("source", ""),
                    "remote_system": remote.get("section", remote.get("system", "")),
                    "has_artwork": bool(remote.get("has_artwork")),
                    "appid": str(remote.get("appid") or ""),
                    "playable": bool(remote.get("playable")),
                    "track_count": int(remote.get("track_count") or 0),
                    "progress": remote.get("progress") or {},
                    "size": remote.get("size") or 0,
                },
                media_type=kind.id,
                media_format=str(remote.get("media_format") or ""),
                category=str(remote.get("category") or ""),
                genres=list(remote.get("genres") or []),
                creators=list(remote.get("creators") or []),
                series=str(remote.get("series") or ""),
                series_index=remote.get("series_index"),
            )
        )
    return games


def get_games(hosts: list[dict], hidden_ids=None, fetcher=None) -> list[Game]:
    games, _statuses = discover(hosts, hidden_ids=hidden_ids, fetcher=fetcher)
    return games
