from __future__ import annotations

from ..models import Game
from ..network import fetch_remote_library


def get_games(
    hosts: list[dict],
    hidden_ids=None,
    fetcher=fetch_remote_library,
) -> list[Game]:
    hidden_ids = hidden_ids or set()
    games = []
    for host in hosts:
        token = host.get("token")
        if not token:
            continue
        try:
            payload = fetcher(host, token)
        except Exception:
            continue
        for remote in payload.get("games", []):
            remote_id = str(remote.get("id", ""))
            title = str(remote.get("title", "")).strip()
            if not remote_id or not title:
                continue
            game_id = f"remote:{host['name']}:{remote_id}"
            if game_id in hidden_ids:
                continue
            games.append(
                Game(
                    id=game_id,
                    title=title,
                    source="remote",
                    subtitle=host["name"],
                    icon_name="network-server-symbolic",
                    extra={
                        "host": dict(host),
                        "remote_id": remote_id,
                        "remote_source": remote.get("source", ""),
                        "remote_system": remote.get("system", ""),
                        "has_artwork": bool(remote.get("has_artwork")),
                    },
                )
            )
    return games
