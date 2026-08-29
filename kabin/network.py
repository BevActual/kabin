from __future__ import annotations

import hmac
import hashlib
import json
import os
import secrets
import shutil
import socket
import ssl
import sys
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .streaming import media_capabilities


SERVICE_TYPE = "_kabin._tcp"
SESSION_TTL = 600


def network_identity_root() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "kabin" / "network"


def ensure_host_certificate(root: Path | None = None) -> tuple[Path, Path, str]:
    directory = root or network_identity_root()
    certificate = directory / "host.crt"
    private_key = directory / "host.key"
    if not certificate.is_file() or not private_key.is_file():
        directory.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-sha256",
                "-nodes", "-days", "3650", "-subj", "/CN=Kabin Host",
                "-keyout", str(private_key), "-out", str(certificate),
            ],
            check=True,
            capture_output=True,
        )
        private_key.chmod(0o600)
        certificate.chmod(0o644)
    der = ssl.PEM_cert_to_DER_cert(certificate.read_text())
    fingerprint = hashlib.sha256(der).hexdigest()
    return certificate, private_key, fingerprint


def serialize_game(game) -> dict:
    """Public catalog representation: deliberately excludes paths and commands."""
    return {
        "id": game.id,
        "title": game.title,
        "source": game.source,
        "system": game.subtitle,
        "has_artwork": bool(game.icon_path),
    }


class _KabinHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError, ssl.SSLError)):
            return
        super().handle_error(request, client_address)


class HostService:
    def __init__(self, config, catalog_provider, tls=True, identity_root=None):
        self.config = config
        self.catalog_provider = catalog_provider
        self.server = None
        self.thread = None
        self.publisher = None
        self.error = None
        self.pairing_code = None
        self.pairing_expires = 0
        self.sessions = {}
        self.session_games = {}
        self.sessions_lock = threading.Lock()
        self.tls = tls
        self.identity_root = identity_root
        self.fingerprint = None

    @property
    def running(self) -> bool:
        return self.server is not None

    @property
    def address(self) -> str:
        port = self.server.server_port if self.server else self.config.network["port"]
        return f"http://0.0.0.0:{port}"

    def start(self):
        if self.running:
            return
        self.config.ensure_network_token()
        host_name = self.config.network["host_name"]
        port = int(self.config.network["port"])
        service = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def _json(self, status, payload):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _image(self, path):
                try:
                    data = Path(path).read_bytes()
                except OSError:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "artwork not found"})
                    return
                if not data or len(data) > 15 * 1024 * 1024:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "artwork not found"})
                    return
                if data.startswith(b"\x89PNG\r\n\x1a\n"):
                    content_type = "image/png"
                elif data.startswith(b"\xff\xd8\xff"):
                    content_type = "image/jpeg"
                elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
                    content_type = "image/webp"
                else:
                    self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "unsupported artwork"})
                    return
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "private, max-age=86400")
                self.end_headers()
                self.wfile.write(data)

            def _authorized(self):
                supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
                return service.config.network_token_valid(supplied)

            def do_GET(self):
                if self.path == "/v1/info":
                    self._json(
                        HTTPStatus.OK,
                        {
                            "protocol": 1,
                            "name": host_name,
                            "service": "Kabin Host",
                            "pairing_required": True,
                        },
                    )
                    return
                if self.path == "/v1/library":
                    if not self._authorized():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
                        return
                    games = [serialize_game(game) for game in service.catalog_provider()]
                    self._json(HTTPStatus.OK, {"games": games, "count": len(games)})
                    return
                if self.path == "/v1/media/capabilities":
                    if not self._authorized():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
                        return
                    self._json(HTTPStatus.OK, media_capabilities())
                    return
                if self.path.startswith("/v1/artwork?"):
                    if not self._authorized():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
                        return
                    query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    game_id = (query.get("id") or [""])[0]
                    game = next(
                        (
                            item
                            for item in service.catalog_provider()
                            if item.id == game_id and item.icon_path
                        ),
                        None,
                    )
                    if not game:
                        self._json(HTTPStatus.NOT_FOUND, {"error": "artwork not found"})
                        return
                    self._image(game.icon_path)
                    return
                if self.path.startswith("/v1/sessions/"):
                    if not self._authorized():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
                        return
                    session_id = self.path.removeprefix("/v1/sessions/")
                    session = service.get_session(session_id)
                    if not session:
                        self._json(HTTPStatus.NOT_FOUND, {"error": "session not found"})
                        return
                    self._json(HTTPStatus.OK, session)
                    return
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

            def do_POST(self):
                if self.path.startswith("/v1/sessions/") and self.path.endswith("/launch"):
                    if not self._authorized():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
                        return
                    session_id = self.path.removeprefix("/v1/sessions/").removesuffix("/launch")
                    status, session = service.activate_session(session_id)
                    self._json(status, session)
                    return
                if self.path == "/v1/sessions":
                    if not self._authorized():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
                        return
                    payload = self._read_payload()
                    if payload is None:
                        return
                    session = service.prepare_session(str(payload.get("game_id", "")))
                    if not session:
                        self._json(HTTPStatus.NOT_FOUND, {"error": "game not found or not launchable"})
                        return
                    self._json(HTTPStatus.CREATED, session)
                    return
                if self.path != "/v1/pair":
                    self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return
                payload = self._read_payload()
                if payload is None:
                    return

                code = str(payload.get("code", ""))
                if not service.consume_pairing_code(code):
                    self._json(HTTPStatus.FORBIDDEN, {"error": "invalid or expired pairing code"})
                    return
                device_name = str(payload.get("device_name", "Kabin device"))[:80]
                device_token = service.config.add_paired_device(device_name)
                self._json(HTTPStatus.CREATED, {"token": device_token, "host": host_name})

            def _read_payload(self):
                try:
                    length = min(int(self.headers.get("Content-Length", "0")), 4096)
                    return json.loads(self.rfile.read(length) or b"{}")
                except (ValueError, json.JSONDecodeError):
                    self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid request"})
                    return None

        try:
            self.server = _KabinHTTPServer(("0.0.0.0", port), Handler)
            if self.tls:
                certificate, private_key, self.fingerprint = ensure_host_certificate(
                    self.identity_root
                )
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(certificate, private_key)
                self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            self.error = str(exc)
            self.server = None
            return
        self.error = None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self._publish(host_name, self.server.server_port)

    def create_pairing_code(self, lifetime=300) -> str:
        self.pairing_code = f"{secrets.randbelow(1_000_000):06d}"
        self.pairing_expires = time.monotonic() + lifetime
        return self.pairing_code

    def consume_pairing_code(self, code: str) -> bool:
        valid = (
            self.pairing_code is not None
            and time.monotonic() <= self.pairing_expires
            and hmac.compare_digest(code, self.pairing_code)
        )
        if valid:
            self.pairing_code = None
            self.pairing_expires = 0
        return valid

    def prepare_session(self, game_id: str) -> dict | None:
        game = next(
            (item for item in self.catalog_provider() if item.id == game_id and item.launch),
            None,
        )
        if game is None:
            return None
        session_id = secrets.token_urlsafe(18)
        session = {
            "id": session_id,
            "game_id": game.id,
            "title": game.title,
            "state": "prepared",
            "created_at": time.time(),
            "media": {"status": "awaiting-negotiation"},
            "capabilities": media_capabilities(),
        }
        with self.sessions_lock:
            self.sessions[session_id] = session
            self.session_games[session_id] = game
        return dict(session)

    def get_session(self, session_id: str) -> dict | None:
        with self.sessions_lock:
            session = self.sessions.get(session_id)
            if not session:
                return None
            if time.time() - session["created_at"] > SESSION_TTL:
                self.sessions.pop(session_id, None)
                self.session_games.pop(session_id, None)
                return None
            return dict(session)

    def mark_media_connected(self, session_id: str) -> bool:
        with self.sessions_lock:
            session = self.sessions.get(session_id)
            if not session or time.time() - session["created_at"] > SESSION_TTL:
                return False
            session["media"]["status"] = "connected"
            session["state"] = "ready"
            return True

    def activate_session(self, session_id: str) -> tuple[int, dict]:
        session = self.get_session(session_id)
        if not session:
            return HTTPStatus.NOT_FOUND, {"error": "session not found or expired"}
        if session["media"]["status"] != "connected":
            return HTTPStatus.CONFLICT, {"error": "media channel is not connected"}
        if session["state"] == "running":
            return HTTPStatus.OK, session
        game = self.session_games.get(session_id)
        if not game or not game.launch:
            return HTTPStatus.GONE, {"error": "game is no longer launchable"}
        try:
            game.launch()
            self.config.record_played(game.id)
        except Exception as exc:
            return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"launch failed: {exc}"}
        with self.sessions_lock:
            self.sessions[session_id]["state"] = "running"
            self.sessions[session_id]["started_at"] = time.time()
            return HTTPStatus.OK, dict(self.sessions[session_id])

    def _publish(self, name, port):
        executable = shutil.which("avahi-publish-service")
        if not executable:
            return
        try:
            metadata = ["protocol=1", f"tls={int(self.tls)}"]
            if self.fingerprint:
                metadata.append(f"fingerprint={self.fingerprint}")
            self.publisher = subprocess.Popen(
                [executable, name, SERVICE_TYPE, str(port), *metadata],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            self.publisher = None

    def stop(self):
        if self.publisher:
            self.publisher.terminate()
            self.publisher = None
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        self.thread = None


def parse_avahi_hosts(output: str) -> list[dict]:
    hosts = []
    seen = set()
    for line in output.splitlines():
        fields = line.split(";")
        if len(fields) < 9 or fields[0] != "=" or fields[4] != SERVICE_TYPE:
            continue
        key = (fields[7], fields[8])
        if key in seen:
            continue
        seen.add(key)
        metadata = {item.split("=", 1)[0]: item.split("=", 1)[1] for item in fields[9:] if "=" in item}
        hosts.append({
            "name": fields[3],
            "address": fields[7],
            "port": int(fields[8]),
            "tls": metadata.get("tls") == "1",
            "fingerprint": metadata.get("fingerprint", ""),
        })
    return hosts


def discover_hosts(timeout=4) -> list[dict]:
    executable = shutil.which("avahi-browse")
    if not executable:
        return []
    try:
        result = subprocess.run(
            [executable, "-rtp", SERVICE_TYPE],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return parse_avahi_hosts(result.stdout)


def host_url(host: dict, path: str) -> str:
    scheme = "https" if host.get("tls", False) else "http"
    return f"{scheme}://{host['address']}:{host['port']}{path}"


def pinned_tls_context(host: dict, timeout=5):
    if not host.get("tls", False):
        return None
    expected = host.get("fingerprint", "")
    if len(expected) != 64:
        raise ssl.SSLError("Kabin Host certificate fingerprint is missing")
    unverified = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    unverified.check_hostname = False
    unverified.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host["address"], int(host["port"])), timeout) as raw:
        with unverified.wrap_socket(raw, server_hostname=host["address"]) as connection:
            certificate = connection.getpeercert(binary_form=True)
    actual = hashlib.sha256(certificate).hexdigest()
    if not hmac.compare_digest(actual, expected):
        raise ssl.SSLError("Kabin Host certificate fingerprint changed")
    context = ssl.create_default_context(cadata=ssl.DER_cert_to_PEM_cert(certificate))
    context.check_hostname = False
    return context


def pair_with_host(host: dict, code: str, device_name: str, timeout=5) -> dict:
    url = host_url(host, "/v1/pair")
    body = json.dumps({"code": code, "device_name": device_name}).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(
        request, timeout=timeout, context=pinned_tls_context(host, timeout)
    ) as response:
        return json.loads(response.read())


def fetch_remote_library(host: dict, token: str, timeout=5) -> dict:
    url = host_url(host, "/v1/library")
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(
        request, timeout=timeout, context=pinned_tls_context(host, timeout)
    ) as response:
        return json.loads(response.read())


def prepare_remote_session(host: dict, token: str, game_id: str, timeout=5) -> dict:
    url = host_url(host, "/v1/sessions")
    body = json.dumps({"game_id": game_id}).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(
        request, timeout=timeout, context=pinned_tls_context(host, timeout)
    ) as response:
        return json.loads(response.read())


def launch_remote_session(host: dict, token: str, session_id: str, timeout=5) -> dict:
    url = host_url(host, f"/v1/sessions/{urllib.parse.quote(session_id, safe='')}/launch")
    request = urllib.request.Request(
        url,
        data=b"{}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(
        request, timeout=timeout, context=pinned_tls_context(host, timeout)
    ) as response:
        return json.loads(response.read())
