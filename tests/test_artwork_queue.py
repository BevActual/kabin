import threading
import unittest

from kabin.artwork_queue import ArtworkQueue


class TestArtworkQueue(unittest.TestCase):
    def test_deduplicates_inflight_requests_and_notifies_every_listener(self):
        release = threading.Event()
        fetched = []
        results = []
        complete = threading.Event()

        def fetcher(host, token, game_id):
            fetched.append((host["name"], token, game_id))
            release.wait(2)
            return "/tmp/cover.png"

        def dispatcher(callback, result):
            callback(result)

        queue = ArtworkQueue(fetcher, dispatcher, max_workers=1)
        host = {"name": "Host", "address": "10.0.0.2", "port": 42424}

        def done(path):
            results.append(path)
            if len(results) == 2:
                complete.set()

        queue.request(host, "token", "game", done)
        queue.request(host, "token", "game", done)
        release.set()
        self.assertTrue(complete.wait(2))
        queue.close()

        self.assertEqual(fetched, [("Host", "token", "game")])
        self.assertEqual(results, ["/tmp/cover.png", "/tmp/cover.png"])

    def test_fetch_errors_return_none_without_stalling_queue(self):
        complete = threading.Event()
        results = []

        def fetcher(*_args):
            raise OSError("offline")

        queue = ArtworkQueue(fetcher, lambda callback, result: callback(result), max_workers=1)
        queue.request({}, "token", "game", lambda result: (results.append(result), complete.set()))
        self.assertTrue(complete.wait(2))
        queue.close()

        self.assertEqual(results, [None])


if __name__ == "__main__":
    unittest.main()
