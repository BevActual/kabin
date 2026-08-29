import unittest

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

    def test_remote_game_defers_transferred_artwork(self):
        host = {"name": "Host", "token": "t"}
        payload = {
            "games": [{"id": "steam:1", "title": "Game", "has_artwork": True}]
        }
        games = remote.get_games([host], fetcher=lambda *_args: payload)
        self.assertIsNone(games[0].icon_path)
        self.assertTrue(games[0].extra["has_artwork"])


if __name__ == "__main__":
    unittest.main()
