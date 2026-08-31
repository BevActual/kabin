from __future__ import annotations

import ssl
import urllib.error

from ..kinds import get_kind
from ..models import Game
from ..network import fetch_remote_library


def discover(
    hosts: list[dict],
    hidden_ids=None,
    fetcher=fetch_remote_library,
) -> tuple[list[Game], dict[str, dict]]:
    hidden_ids = hidden_ids or set()
    games = []
    statuses = {}
    for host in hosts:
        name = host.get("name", "Kabin Host")
        token = host.get("token")
        if not token:
            statuses[name] = {"state": "auth", "message": "Pairing required"}
            continue
        try:
            payload = fetcher(host, token)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                statuses[name] = {"state": "auth", "message": "Re-pair required"}
            else:
                statuses[name] = {"state": "offline", "message": f"HTTP {exc.code}"}
            exc.close()
            continue
        except ssl.SSLError:
            statuses[name] = {"state": "auth", "message": "Host identity changed"}
            continue
        except (OSError, TimeoutError) as exc:
            statuses[name] = {"state": "offline", "message": str(exc) or "Unavailable"}
            continue
        except Exception as exc:
            statuses[name] = {"state": "offline", "message": str(exc) or "Unavailable"}
            continue
        statuses[name] = {"state": "online", "message": "Online"}
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
    return games, statuses


def get_games(hosts: list[dict], hidden_ids=None, fetcher=fetch_remote_library) -> list[Game]:
    games, _statuses = discover(hosts, hidden_ids=hidden_ids, fetcher=fetcher)
    return games
