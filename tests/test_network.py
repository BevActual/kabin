import json
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
)


class TestNetwork(unittest.TestCase):
    def test_public_catalog_does_not_expose_paths_or_launch_commands(self):
        game = SimpleNamespace(
            id="roms:gba:test.gba",
            title="Test",
            source="roms",
            subtitle="Game Boy Advance",
            icon_path="/private/cover.png",
            extra={"path": "/private/test.gba"},
            launch=lambda: None,
        )
        public = serialize_game(game)
        self.assertEqual(public["title"], "Test")
        self.assertNotIn("extra", public)
        self.assertNotIn("launch", public)

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


if __name__ == "__main__":
    unittest.main()
