import threading
import unittest
import urllib.error

from kabin.sources import remote


class TestRemoteSource(unittest.TestCase):
    def test_turns_remote_catalog_into_kabin_games(self):
        host = {"name": "Gaming PC", "address": "10.0.0.2", "port": 42424, "token": "t"}

        def fetcher(_host, _token):
            return {
                "games": [
                    {
                        "id": "roms:gba:test.gba",
                        "title": "Remote Game",
                        "source": "roms",
                        "system": "Game Boy Advance",
                    }
                ]
            }

        games = remote.get_games([host], fetcher=fetcher)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].source, "remote")
        self.assertEqual(games[0].subtitle, "Gaming PC")
        self.assertEqual(games[0].extra["remote_system"], "Game Boy Advance")
        self.assertIsNone(games[0].launch)

    def test_offline_host_does_not_break_local_discovery(self):
        host = {"name": "Offline", "token": "t"}

        def fetcher(_host, _token):
            raise OSError("offline")

        self.assertEqual(remote.get_games([host], fetcher=fetcher), [])

        games, statuses = remote.discover([host], fetcher=fetcher)
        self.assertEqual(games, [])
        self.assertEqual(statuses["Offline"]["state"], "offline")

    def test_authentication_failure_requests_repair(self):
        host = {"name": "Host", "token": "expired"}

        def fetcher(_host, _token):
            raise urllib.error.HTTPError("https://host", 401, "Unauthorized", {}, None)

        _games, statuses = remote.discover([host], fetcher=fetcher)
        self.assertEqual(statuses["Host"]["state"], "auth")
        self.assertEqual(statuses["Host"]["message"], "Re-pair required")

    def test_successful_host_is_reported_online(self):
        host = {"name": "Host", "token": "token"}
        _games, statuses = remote.discover(
            [host], fetcher=lambda *_args: {"games": []}
        )
        self.assertEqual(statuses["Host"]["state"], "online")

    def test_hosts_are_queried_concurrently_and_results_keep_host_order(self):
        # A powered-off host costs a full connect timeout. Querying hosts
        # one after another made every refresh wait timeout × N.
        hosts = [
            {"name": "Slow", "token": "t"},
            {"name": "Fast", "token": "t"},
            {"name": "Down", "token": "t"},
        ]
        started = threading.Barrier(3, timeout=2)

        def fetcher(host, _token):
            # Only passes if all three fetches are in flight at once.
            started.wait()
            if host["name"] == "Down":
                raise OSError("no route to host")
            return {"games": [{"id": f"steam:{host['name']}", "title": host["name"]}]}

        games, statuses = remote.discover(hosts, fetcher=fetcher)
        self.assertEqual([game.title for game in games], ["Slow", "Fast"])
        self.assertEqual(
            [statuses[name]["state"] for name in ("Slow", "Fast", "Down")],
            ["online", "online", "offline"],
        )

    def test_no_hosts_is_a_no_op(self):
        self.assertEqual(remote.discover([]), ([], {}))

    def test_remote_game_defers_transferred_artwork(self):
        host = {"name": "Host", "token": "t"}
        payload = {
            "games": [{"id": "steam:1", "title": "Game", "has_artwork": True}]
        }
        games = remote.get_games([host], fetcher=lambda *_args: payload)
        self.assertIsNone(games[0].icon_path)
        self.assertTrue(games[0].extra["has_artwork"])

    def test_remote_steam_game_keeps_appid_for_cdn_covers(self):
        host = {"name": "Host", "token": "t"}
        payload = {
            "games": [{"id": "steam:1", "title": "Game", "source": "steam", "appid": "1"}]
        }
        games = remote.get_games([host], fetcher=lambda *_args: payload)
        self.assertEqual(games[0].extra["appid"], "1")

    def test_remote_catalog_keeps_books_and_games(self):
        host = {"name": "Host", "token": "t"}
        payload = {
            "items": [
                {
                    "id": "book:1",
                    "title": "Book",
                    "media_type": "book",
                    "creators": ["Author"],
                },
                {"id": "steam:1", "title": "Game", "media_type": "game"},
            ]
        }
        games = remote.get_games([host], fetcher=lambda *_args: payload)
        self.assertEqual([game.title for game in games], ["Book", "Game"])
        self.assertEqual(games[0].media_type, "book")
        self.assertEqual(games[0].creators, ["Author"])
        self.assertFalse(games[0].extra["playable"])

    def test_remote_catalog_keeps_playable_flag(self):
        host = {"name": "Host", "token": "t"}
        payload = {
            "items": [
                {
                    "id": "video:1",
                    "title": "Film",
                    "media_type": "video",
                    "playable": True,
                    "track_count": 1,
                    "progress": {"position": 12, "duration": 100, "track": 0, "updated_at": 1},
                }
            ]
        }
        games = remote.get_games([host], fetcher=lambda *_args: payload)
        self.assertTrue(games[0].extra["playable"])
        self.assertEqual(games[0].media_type, "video")
        self.assertEqual(games[0].extra["track_count"], 1)
        self.assertEqual(games[0].extra["progress"]["position"], 12)


if __name__ == "__main__":
    unittest.main()
