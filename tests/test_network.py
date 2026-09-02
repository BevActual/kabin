import json
import socket
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kabin.config import Config
from kabin.network import (
    HostService,
    SESSION_TTL,
    ensure_host_certificate,
    fetch_remote_library,
    pair_with_host,
    parse_avahi_hosts,
    prepare_remote_session,
    serialize_game,
    signal_remote_session,
)
from kabin.playback import save_progress


class TestNetwork(unittest.TestCase):
    def test_public_catalog_does_not_expose_paths_or_launch_commands(self):
        game = SimpleNamespace(
            id="roms:gba:test.gba",
            title="Test",
            source="roms",
            subtitle="Game Boy Advance",
            icon_path="/private/cover.png",
            extra={"path": "/private/test.gba", "appid": ""},
            launch=lambda: None,
        )
        public = serialize_game(game)
        self.assertEqual(public["title"], "Test")
        self.assertEqual(public["media_type"], "game")
        self.assertEqual(public["section"], "Game Boy Advance")
        self.assertEqual(public["genres"], [])
        self.assertEqual(public["creators"], [])
        self.assertNotIn("extra", public)
        self.assertNotIn("launch", public)
        self.assertEqual(public["appid"], "")
        self.assertTrue(public["has_artwork"])
        self.assertFalse(public["playable"])

        steam = SimpleNamespace(
            id="steam:1",
            title="Steam Game",
            source="steam",
            subtitle="Steam",
            icon_path=None,
            extra={"appid": "1"},
        )
        self.assertEqual(serialize_game(steam)["appid"], "1")
        self.assertTrue(serialize_game(steam)["has_artwork"])

    def test_parses_resolved_avahi_service(self):
        output = "=;eth0;IPv4;Living Room;_kabin._tcp;local;host.local;192.168.1.5;42424;protocol=1"
        self.assertEqual(
            parse_avahi_hosts(output),
            [{
                "name": "Living Room",
                "address": "192.168.1.5",
                "port": 42424,
                "tls": False,
                "fingerprint": "",
            }],
        )

    def test_tls_host_is_reachable_only_with_pinned_certificate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = Config(path=root / "config.json")
            config.network["port"] = 0
            game = SimpleNamespace(
                id="steam:1", title="Game", source="steam", subtitle="Steam", icon_path=None
            )
            service = HostService(config, lambda: [game], tls=True, identity_root=root / "identity")
            with patch.object(service, "_publish"):
                service.start()
            self.addCleanup(service.stop)
            self.assertTrue(service.fingerprint)
            host = {
                "name": "Secure Host",
                "address": "127.0.0.1",
                "port": service.server.server_port,
                "tls": True,
                "fingerprint": service.fingerprint,
            }
            payload = fetch_remote_library(host, config.ensure_network_token())
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["counts"], {"game": 1})
            self.assertEqual(payload["items"], payload["games"])
            host["fingerprint"] = "0" * 64
            with self.assertRaisesRegex(Exception, "fingerprint changed"):
                fetch_remote_library(host, config.ensure_network_token())

    def test_generated_private_key_is_owner_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            _certificate, private_key, fingerprint = ensure_host_certificate(Path(tmp))
            self.assertEqual(private_key.stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(fingerprint), 64)

    def test_library_requires_bearer_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            config.network["port"] = 0
            game = SimpleNamespace(
                id="steam:1", title="Game", source="steam", subtitle="Steam", icon_path=None
            )
            service = HostService(config, lambda: [game], tls=False)
            with patch.object(service, "_publish"):
                service.start()
            self.addCleanup(service.stop)
            url = f"http://127.0.0.1:{service.server.server_port}/v1/library"
            with self.assertRaises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(url)
            self.assertEqual(denied.exception.code, 401)
            denied.exception.close()

            request = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {config.network['token']}"}
            )
            with urllib.request.urlopen(request) as response:
                payload = json.loads(response.read())
            self.assertEqual(payload["count"], 1)

    def test_one_time_code_issues_device_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            config.network["port"] = 0
            game = SimpleNamespace(
                id="steam:1", title="Game", source="steam", subtitle="Steam", icon_path=None
            )
            service = HostService(config, lambda: [game], tls=False)
            with patch.object(service, "_publish"):
                service.start()
            self.addCleanup(service.stop)
            host = {
                "name": "Host",
                "address": "127.0.0.1",
                "port": service.server.server_port,
            }
            code = service.create_pairing_code()
            pairing = pair_with_host(host, code, "Living Room")
            self.assertTrue(config.network_token_valid(pairing["token"]))
            self.assertEqual(fetch_remote_library(host, pairing["token"])["count"], 1)
            with self.assertRaises(urllib.error.HTTPError) as reused:
                pair_with_host(host, code, "Other device")
            self.assertEqual(reused.exception.code, 403)
            reused.exception.close()

    def test_signal_negotiates_kabin_stream_and_launches_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            config.network["port"] = 0
            launched = []
            game = SimpleNamespace(
                id="steam:1",
                title="Game",
                source="steam",
                subtitle="Steam",
                icon_path=None,
                launch=lambda: launched.append(True),
            )
            service = HostService(config, lambda: [game], tls=False)
            with patch.object(service, "_publish"):
                service.start()
            self.addCleanup(service.stop)
            host = {
                "name": "Host",
                "address": "127.0.0.1",
                "port": service.server.server_port,
            }
            token = config.ensure_network_token()
            with patch(
                "kabin.network.stream_offer",
                return_value={
                    "status": "awaiting-negotiation",
                    "protocol": "kabin",
                    "transport": "webrtc",
                },
            ):
                session = prepare_remote_session(host, token, game.id)
            self.assertEqual(session["state"], "prepared")
            self.assertEqual(session["media"]["protocol"], "kabin")
            self.assertEqual(launched, [])
            with patch("kabin.network.MediaHelperSession") as helper_cls, patch(
                "kabin.network.answer_host_offer", return_value="v=0 answer"
            ):
                answer = signal_remote_session(host, token, session["id"], "v=0 offer")
            helper_cls.assert_called_once_with("host")
            self.assertEqual(answer["type"], "answer")
            self.assertEqual(answer["sdp"], "v=0 answer")
            self.assertEqual(launched, [True])

    def test_signal_accepts_realistic_multi_candidate_sdp_offers(self):
        # A real WebRTC offer with several ICE candidates and codec lines routinely
        # exceeds a few KB; the request-body cap must not silently truncate it.
        large_sdp = "v=0\r\no=- 1 1 IN IP4 0.0.0.0\r\ns=-\r\nt=0 0\r\n" + (
            "a=candidate:1 1 udp 2 10.0.0.1 5000 typ host\r\n" * 120
        )
        self.assertGreater(len(large_sdp), 4096)
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            config.network["port"] = 0
            game = SimpleNamespace(
                id="steam:1",
                title="Game",
                source="steam",
                subtitle="Steam",
                icon_path=None,
                launch=lambda: None,
            )
            service = HostService(config, lambda: [game], tls=False)
            with patch.object(service, "_publish"):
                service.start()
            self.addCleanup(service.stop)
            host = {"name": "Host", "address": "127.0.0.1", "port": service.server.server_port}
            token = config.ensure_network_token()
            with patch(
                "kabin.network.stream_offer",
                return_value={"status": "awaiting-negotiation", "protocol": "kabin", "transport": "webrtc"},
            ):
                session = prepare_remote_session(host, token, game.id)
            with patch("kabin.network.MediaHelperSession"), patch(
                "kabin.network.answer_host_offer", return_value="v=0 answer"
            ) as answer_host_offer:
                answer = signal_remote_session(host, token, session["id"], large_sdp)
            self.assertEqual(answer["sdp"], "v=0 answer")
            self.assertEqual(answer_host_offer.call_args.args[1], large_sdp)

    def test_remote_session_is_prepared_without_launching_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            config.network["port"] = 0
            launched = []
            game = SimpleNamespace(
                id="roms:gba:test.gba",
                title="Remote Game",
                source="roms",
                subtitle="Game Boy Advance",
                icon_path=None,
                launch=lambda: launched.append(True),
            )
            service = HostService(config, lambda: [game], tls=False)
            with patch.object(service, "_publish"):
                service.start()
            self.addCleanup(service.stop)
            host = {
                "name": "Host",
                "address": "127.0.0.1",
                "port": service.server.server_port,
            }
            token = config.ensure_network_token()
            with patch(
                "kabin.network.stream_offer",
                return_value={"status": "awaiting-negotiation", "protocol": "webrtc"},
            ):
                session = prepare_remote_session(host, token, game.id)
            self.assertEqual(session["state"], "prepared")
            self.assertEqual(session["media"]["status"], "awaiting-negotiation")
            self.assertEqual(launched, [])

    def test_remote_session_rejects_unknown_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            config.network["port"] = 0
            service = HostService(config, lambda: [], tls=False)
            with patch.object(service, "_publish"):
                service.start()
            self.addCleanup(service.stop)
            host = {
                "name": "Host",
                "address": "127.0.0.1",
                "port": service.server.server_port,
            }
            with self.assertRaises(urllib.error.HTTPError) as missing:
                prepare_remote_session(host, config.ensure_network_token(), "missing")
            self.assertEqual(missing.exception.code, 404)
            missing.exception.close()

    def test_session_cannot_launch_before_media_connects(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            launched = []
            game = SimpleNamespace(
                id="steam:1",
                title="Game",
                source="steam",
                subtitle="Steam",
                icon_path=None,
                launch=lambda: launched.append(True),
            )
            service = HostService(config, lambda: [game], tls=False)
            with patch(
                "kabin.network.stream_offer",
                return_value={"status": "awaiting-negotiation", "protocol": "webrtc"},
            ):
                session = service.prepare_session(game.id)
            status, payload = service.activate_session(session["id"])
            self.assertEqual(status, 409)
            self.assertIn("media", payload["error"])
            self.assertEqual(launched, [])

            self.assertTrue(service.mark_media_connected(session["id"]))
            status, payload = service.activate_session(session["id"])
            self.assertEqual(status, 200)
            self.assertEqual(payload["state"], "running")
            self.assertEqual(launched, [True])
            service.activate_session(session["id"])
            self.assertEqual(launched, [True])

    def test_prepared_session_expires(self):
        game = SimpleNamespace(
            id="steam:1",
            title="Game",
            source="steam",
            launch=lambda: None,
        )
        with tempfile.TemporaryDirectory() as tmp:
            service = HostService(
                Config(path=Path(tmp) / "config.json"), lambda: [game], tls=False
            )
            session = service.prepare_session(game.id)
            service.sessions[session["id"]]["created_at"] -= SESSION_TTL + 1
            self.assertIsNone(service.get_session(session["id"]))
            self.assertNotIn(session["id"], service.session_games)

    def test_artwork_endpoint_requires_authentication_and_hides_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cover = root / "secret-name.png"
            cover.write_bytes(b"\x89PNG\r\n\x1a\nimage")
            config = Config(path=root / "config.json")
            config.network["port"] = 0
            game = SimpleNamespace(
                id="roms:gba:test.gba",
                title="Game",
                source="roms",
                subtitle="GBA",
                icon_path=str(cover),
            )
            service = HostService(config, lambda: [game], tls=False)
            with patch.object(service, "_publish"):
                service.start()
            self.addCleanup(service.stop)
            url = (
                f"http://127.0.0.1:{service.server.server_port}"
                "/v1/artwork?id=roms%3Agba%3Atest.gba"
            )
            with self.assertRaises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(url)
            denied.exception.close()
            request = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {config.ensure_network_token()}"},
            )
            with urllib.request.urlopen(request) as response:
                self.assertEqual(response.read(), cover.read_bytes())
                self.assertEqual(response.headers["Content-Type"], "image/png")

    def test_artwork_endpoint_refuses_symlinked_covers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = root / "secret.txt"
            secret.write_text("private")
            cover = root / "Game.png"
            cover.symlink_to(secret)
            config = Config(path=root / "config.json")
            config.network["port"] = 0
            game = SimpleNamespace(
                id="roms:gba:Game.gba",
                title="Game",
                source="roms",
                subtitle="GBA",
                icon_path=str(cover),
            )
            service = HostService(config, lambda: [game], tls=False)
            with patch.object(service, "_publish"):
                service.start()
            self.addCleanup(service.stop)
            request = urllib.request.Request(
                f"http://127.0.0.1:{service.server.server_port}/v1/artwork?id=roms%3Agba%3AGame.gba",
                headers={"Authorization": f"Bearer {config.ensure_network_token()}"},
            )
            with self.assertRaises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(request)
            self.assertEqual(denied.exception.code, 404)
            denied.exception.close()

    def test_media_stream_serves_range_without_exposing_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "films"
            library.mkdir()
            media = library / "film.mkv"
            media.write_bytes(b"0123456789")
            config = Config(path=Path(tmp) / "config.json")
            config.network["port"] = 0
            config.media_dirs.append({"path": str(library), "media_type": "video"})
            item = SimpleNamespace(
                id="video:film.mkv",
                title="Film",
                source="video",
                subtitle="Movie",
                icon_path=None,
                extra={"path": str(media)},
                media_type="video",
            )
            service = HostService(config, lambda: [item], tls=False)
            with patch.object(service, "_publish"):
                service.start()
            self.addCleanup(service.stop)
            token = config.ensure_network_token()
            catalog_request = urllib.request.Request(
                f"http://127.0.0.1:{service.server.server_port}/v1/library",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(catalog_request) as response:
                catalog = json.loads(response.read())
            self.assertTrue(catalog["items"][0]["playable"])
            self.assertEqual(catalog["items"][0]["track_count"], 1)
            self.assertEqual(catalog["items"][0]["progress"]["position"], 0)
            self.assertNotIn("path", catalog["items"][0])
            self.assertNotIn(str(media), json.dumps(catalog))

            url = f"http://127.0.0.1:{service.server.server_port}/v1/media/stream?id=video:film.mkv"
            with self.assertRaises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(url)
            self.assertEqual(denied.exception.code, 401)
            denied.exception.close()

            request = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {token}", "Range": "bytes=2-5"},
            )
            with urllib.request.urlopen(request) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(response.read(), b"2345")
                self.assertEqual(response.headers.get("Content-Range"), "bytes 2-5/10")

    def test_library_exposes_progress_for_book_and_comic_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "books"
            library.mkdir()
            book_path = library / "novel.epub"
            book_path.write_bytes(b"pk")
            config = Config(path=Path(tmp) / "config.json")
            config.network["port"] = 0
            book = SimpleNamespace(
                id="book:novel.epub",
                title="Novel",
                source="book",
                subtitle="Book",
                icon_path=None,
                extra={"path": str(book_path)},
                media_type="book",
            )
            game = SimpleNamespace(
                id="steam:1",
                title="Game",
                source="steam",
                subtitle="Steam",
                icon_path=None,
                extra={},
                media_type="game",
            )
            save_progress(config, "book:novel.epub", 12, 40)
            service = HostService(config, lambda: [book, game], tls=False)
            with patch.object(service, "_publish"):
                service.start()
            self.addCleanup(service.stop)
            token = config.ensure_network_token()
            request = urllib.request.Request(
                f"http://127.0.0.1:{service.server.server_port}/v1/library",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(request) as response:
                catalog = json.loads(response.read())
            by_id = {item["id"]: item for item in catalog["items"]}
            self.assertEqual(by_id["book:novel.epub"]["progress"]["position"], 12)
            self.assertNotIn("progress", by_id["steam:1"])

    def test_media_stream_serves_album_tracks_and_stores_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "music"
            album = library / "LP"
            album.mkdir(parents=True)
            (album / "a.flac").write_bytes(b"track-a")
            (album / "b.flac").write_bytes(b"track-b")
            config = Config(path=Path(tmp) / "config.json")
            config.network["port"] = 0
            config.media_dirs.append({"path": str(library), "media_type": "music"})
            item = SimpleNamespace(
                id="music:LP",
                title="LP",
                source="music",
                subtitle="Music",
                icon_path=None,
                extra={"path": str(album), "track_count": 2},
                media_type="music",
            )
            service = HostService(config, lambda: [item], tls=False)
            with patch.object(service, "_publish"):
                service.start()
            self.addCleanup(service.stop)
            token = config.ensure_network_token()
            host = "127.0.0.1"
            port = service.server.server_port
            track = urllib.request.Request(
                f"http://{host}:{port}/v1/media/stream?id=music:LP&track=1",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(track) as response:
                self.assertEqual(response.read(), b"track-b")
            body = json.dumps(
                {"id": "music:LP", "position": 42, "duration": 180, "track": 1}
            ).encode()
            progress = urllib.request.Request(
                f"http://{host}:{port}/v1/media/progress",
                data=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(progress) as response:
                stored = json.loads(response.read())
            self.assertEqual(stored["position"], 42)
            self.assertEqual(stored["track"], 1)
            catalog_request = urllib.request.Request(
                f"http://{host}:{port}/v1/library",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(catalog_request) as response:
                catalog = json.loads(response.read())
            self.assertEqual(catalog["items"][0]["progress"]["position"], 42)
            self.assertEqual(catalog["items"][0]["track_count"], 2)

    def test_media_stream_refuses_files_outside_media_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "films"
            library.mkdir()
            outside = Path(tmp) / "secret.mkv"
            outside.write_bytes(b"secret")
            config = Config(path=Path(tmp) / "config.json")
            config.network["port"] = 0
            config.media_dirs.append({"path": str(library), "media_type": "video"})
            item = SimpleNamespace(
                id="video:secret.mkv",
                title="Secret",
                source="video",
                subtitle="Movie",
                icon_path=None,
                extra={"path": str(outside)},
                media_type="video",
            )
            service = HostService(config, lambda: [item], tls=False)
            with patch.object(service, "_publish"):
                service.start()
            self.addCleanup(service.stop)
            request = urllib.request.Request(
                f"http://127.0.0.1:{service.server.server_port}/v1/media/stream?id=video:secret.mkv",
                headers={"Authorization": f"Bearer {config.ensure_network_token()}"},
            )
            with self.assertRaises(urllib.error.HTTPError) as missing:
                urllib.request.urlopen(request)
            self.assertEqual(missing.exception.code, 404)
            missing.exception.close()

    def test_negative_content_length_is_rejected_instead_of_hanging(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            config.network["port"] = 0
            service = HostService(config, lambda: [], tls=False)
            with patch.object(service, "_publish"):
                service.start()
            self.addCleanup(service.stop)

            with socket.create_connection(
                ("127.0.0.1", service.server.server_port), timeout=5
            ) as sock:
                sock.sendall(
                    b"POST /v1/pair HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\n"
                    b"Content-Length: -1\r\n"
                    b"Connection: close\r\n\r\n"
                )
                sock.settimeout(5)
                response = sock.recv(200)
        self.assertIn(b"400", response)

    def test_pairing_locks_after_repeated_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = HostService(
                Config(path=Path(tmp) / "config.json"), lambda: [], tls=False
            )
            service.create_pairing_code()
            for _ in range(8):
                self.assertEqual(service.attempt_pairing("000000"), "invalid")
            self.assertEqual(service.attempt_pairing("000000"), "locked")
            self.assertEqual(service.attempt_pairing(service.pairing_code or ""), "locked")


if __name__ == "__main__":
    unittest.main()
