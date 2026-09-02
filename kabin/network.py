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

from .kinds import kind_for
from .media import MediaHelperError, MediaHelperSession, answer_host_offer
from .playback import (
    is_safe_media_file,
    playable_tracks,
    plays_in_kabin,
    progress_for,
    public_progress,
    save_progress,
    track_count,
)
from .reader import READABLE_KINDS
from .streaming import media_capabilities, stream_offer


def parse_byte_range(range_header: str, size: int) -> tuple[str, int, int]:
    """Resolve one RFC 7233 byte range against a known file size.

    Returns ("full", 0, size - 1) to serve the whole file (no range, a
    range we don't handle, or a malformed one - which RFC 7233 says to
    ignore rather than reject), ("partial", start, end) inclusive, or
    ("unsatisfiable", 0, 0) for a range that starts past the end.

    The previous inline parsing got suffix ranges backwards - "bytes=-5"
    means the *last* five bytes, but it served the first six - and
    answered 206 with a nonsensical Content-Range for ranges past EOF
    instead of 416.
    """
    full = ("full", 0, max(0, size - 1))
    if not size or not range_header.startswith("bytes="):
        return full
    spec = range_header.removeprefix("bytes=").strip()
    if "," in spec:
        # Multiple ranges would need multipart/byteranges; serving the
        # whole entity instead is allowed.
        return full
    start_text, separator, end_text = spec.partition("-")
    if not separator:
        return full
    try:
        if not start_text:
            suffix = int(end_text)
            if suffix <= 0:
                return full
            return ("partial", max(0, size - suffix), size - 1)
        start = int(start_text)
        end = int(end_text) if end_text else size - 1
    except ValueError:
        return full
    if start < 0 or end < 0:
        return full
    if start >= size:
        return ("unsatisfiable", 0, 0)
    end = min(end, size - 1)
    if end < start:
        return ("unsatisfiable", 0, 0)
    return ("partial", start, end)


def _pairing_bytes(value) -> bytes:
    """Bytes for a constant-time compare.

    hmac.compare_digest refuses non-ASCII str outright, and the code comes
    straight from a JSON body, so a single accented character used to
    raise TypeError mid-request: the client saw a dropped connection
    instead of "invalid code", and - because it raised before the failure
    was recorded - the attempt escaped rate-limit accounting entirely.
    """
    return str(value).encode("utf-8", "surrogatepass")


def _tracks_progress(item) -> bool:
    """Whether the host should publish `item`'s saved position in the
    public catalog — video/music (play position) and book/comic (page
    position) alike. Read-only: books/comics aren't streamed the way
    video/music are, so there's no POST /v1/media/progress path for them —
    a paired device with its own local copy of the same file pulls this
    from the catalog and adopts it onto that local copy instead (see
    reader.sync_progress_from_remote)."""
    return plays_in_kabin(item) or kind_for(item).id in READABLE_KINDS


SERVICE_TYPE = "_kabin._tcp"
SESSION_TTL = 600
# Streaming sessions are one-at-a-time in practice; the cap only exists so
# a client that keeps retrying (or a hostile paired device) can't pile them
# up without bound.
MAX_SESSIONS = 32
PAIR_WINDOW = 30
PAIR_MAX_FAILURES = 8
MAX_PAYLOAD_BYTES = 65536  # WebRTC offers with several ICE candidates can exceed a few KB


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


def serialize_item(item, media_dirs=None, progress=None) -> dict:
    """Public catalog representation: deliberately excludes paths and commands."""
    media_type = getattr(item, "media_type", "game")
    extra = getattr(item, "extra", None) or {}
    appid = str(extra.get("appid") or "")
    public = {
        "id": item.id,
        "title": item.title,
        "media_type": media_type,
        "media_format": getattr(item, "media_format", ""),
        "category": getattr(item, "category", ""),
        "genres": list(getattr(item, "genres", [])),
        "creators": list(getattr(item, "creators", [])),
        "series": getattr(item, "series", ""),
        "series_index": getattr(item, "series_index", None),
        "source": item.source,
        "section": item.subtitle,
        "system": item.subtitle if media_type == "game" else "",
        "appid": appid,
        "has_artwork": bool(getattr(item, "icon_path", None)) or bool(appid),
        "playable": plays_in_kabin(item) and media_file_for_item(item, media_dirs) is not None,
        "track_count": track_count(item) if plays_in_kabin(item) else 0,
    }
    if progress is not None:
        public["progress"] = public_progress(progress)
        if kind_for(item).id in READABLE_KINDS:
            # Reading progress is matched across devices by item id, which
            # is a *relative path* - so two differently-organised libraries
            # can collide on a common name ("01.cbz", "book.pdf") and adopt
            # each other's position. Publishing the size lets the other
            # side confirm it's actually the same file. Not path-revealing.
            public["size"] = _item_size(item)
    return public


def _item_size(item) -> int:
    raw = (getattr(item, "extra", None) or {}).get("path")
    if not raw:
        return 0
    try:
        return Path(raw).stat().st_size
    except OSError:
        return 0


def serialize_game(game, media_dirs=None, progress=None) -> dict:
    """Backward-compatible name for callers using the v1 game catalog."""
    return serialize_item(game, media_dirs, progress)


def _catalog_counts(items: list[dict]) -> dict[str, int]:
    counts = {}
    for item in items:
        media_type = item.get("media_type", "unknown")
        counts[media_type] = counts.get(media_type, 0) + 1
    return counts


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
        self.session_helpers = {}
        self.sessions_lock = threading.Lock()
        self._pair_failures: list[float] = []
        self.tls = tls
        self.identity_root = identity_root
        self.fingerprint = None

    @property
    def running(self) -> bool:
        return self.server is not None

    @property
    def address(self) -> str:
        port = self.server.server_port if self.server else self.config.network["port"]
        scheme = "https" if self.tls else "http"
        return f"{scheme}://0.0.0.0:{port}"

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
                if not is_safe_artwork_file(path):
                    self._json(HTTPStatus.NOT_FOUND, {"error": "artwork not found"})
                    return
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

            def _stream_file(self, path: Path):
                try:
                    size = path.stat().st_size
                    handle = path.open("rb")
                except OSError:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "media not found"})
                    return
                kind, start, end = parse_byte_range(self.headers.get("Range", ""), size)
                if kind == "unsatisfiable":
                    handle.close()
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                length = max(0, end - start + 1)
                status = (
                    HTTPStatus.PARTIAL_CONTENT if kind == "partial" else HTTPStatus.OK
                )
                self.send_response(status)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                if status == HTTPStatus.PARTIAL_CONTENT:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Cache-Control", "private, no-transform")
                self.end_headers()
                try:
                    handle.seek(start)
                    remaining = length
                    while remaining:
                        chunk = handle.read(min(64 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                finally:
                    handle.close()

            def _authorized(self):
                supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
                return service.config.network_token_valid(supplied)

            def do_GET(self):
                if self.path == "/v1/info":
                    capabilities = media_capabilities()
                    self._json(
                        HTTPStatus.OK,
                        {
                            "protocol": 1,
                            "name": host_name,
                            "service": "Kabin Host",
                            "pairing_required": True,
                            "streaming": capabilities.get("backend", "none"),
                            "media_ready": bool(capabilities.get("ready")),
                        },
                    )
                    return
                if self.path == "/v1/library":
                    if not self._authorized():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
                        return
                    items = [
                        serialize_item(
                            item,
                            service.config.media_dirs,
                            progress_for(service.config, item.id) if _tracks_progress(item) else None,
                        )
                        for item in service.catalog_provider()
                    ]
                    games = [item for item in items if item["media_type"] == "game"]
                    self._json(
                        HTTPStatus.OK,
                        {
                            "items": items,
                            "games": games,
                            "count": len(items),
                            "counts": _catalog_counts(items),
                        },
                    )
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
                        (item for item in service.catalog_provider() if item.id == game_id),
                        None,
                    )
                    artwork_path = artwork_file_for_item(game) if game else None
                    if not artwork_path:
                        self._json(HTTPStatus.NOT_FOUND, {"error": "artwork not found"})
                        return
                    self._image(artwork_path)
                    return
                if self.path.startswith("/v1/media/progress"):
                    if not self._authorized():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
                        return
                    query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    item_id = (query.get("id") or [""])[0]
                    if item_id:
                        self._json(HTTPStatus.OK, {"id": item_id, **progress_for(service.config, item_id)})
                        return
                    catalog_ids = {entry.id for entry in service.catalog_provider()}
                    payload = {
                        item_id: public_progress(info)
                        for item_id, info in (
                            (entry_id, progress_for(service.config, entry_id))
                            for entry_id in catalog_ids
                        )
                        if info["updated_at"]
                    }
                    self._json(HTTPStatus.OK, {"progress": payload})
                    return
                if self.path.startswith("/v1/media/stream"):
                    if not self._authorized():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
                        return
                    query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    item_id = (query.get("id") or [""])[0]
                    try:
                        track = int((query.get("track") or ["0"])[0] or 0)
                    except ValueError:
                        track = 0
                    item = next(
                        (entry for entry in service.catalog_provider() if entry.id == item_id),
                        None,
                    )
                    media_path = (
                        media_file_for_item(item, service.config.media_dirs, track) if item else None
                    )
                    if not media_path:
                        self._json(HTTPStatus.NOT_FOUND, {"error": "media not found"})
                        return
                    self._stream_file(Path(media_path))
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
                if self.path.startswith("/v1/sessions/") and self.path.endswith("/signal"):
                    if not self._authorized():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
                        return
                    session_id = self.path.removeprefix("/v1/sessions/").removesuffix("/signal")
                    payload = self._read_payload()
                    if payload is None:
                        return
                    if payload.get("type") != "offer" or not payload.get("sdp"):
                        self._json(HTTPStatus.BAD_REQUEST, {"error": "offer sdp is required"})
                        return
                    try:
                        answer = service.negotiate_offer(session_id, str(payload["sdp"]))
                    except MediaHelperError as exc:
                        self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
                        return
                    if not answer:
                        self._json(HTTPStatus.NOT_FOUND, {"error": "session not found"})
                        return
                    service.activate_session(session_id)
                    self._json(HTTPStatus.OK, {"type": "answer", "sdp": answer})
                    return
                if self.path.startswith("/v1/sessions/") and self.path.endswith("/launch"):
                    if not self._authorized():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
                        return
                    session_id = self.path.removeprefix("/v1/sessions/").removesuffix("/launch")
                    status, session = service.activate_session(session_id)
                    self._json(status, session)
                    return
                if self.path == "/v1/media/progress":
                    if not self._authorized():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
                        return
                    payload = self._read_payload()
                    if payload is None:
                        return
                    item_id = str(payload.get("id") or "")
                    item = next(
                        (entry for entry in service.catalog_provider() if entry.id == item_id),
                        None,
                    )
                    if not item or not plays_in_kabin(item):
                        self._json(HTTPStatus.NOT_FOUND, {"error": "media not found"})
                        return
                    save_progress(
                        service.config,
                        item.id,
                        payload.get("position") or 0,
                        payload.get("duration") or 0,
                        payload.get("track") or 0,
                    )
                    self._json(HTTPStatus.OK, {"id": item.id, **progress_for(service.config, item.id)})
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
                pairing = service.attempt_pairing(code)
                if pairing == "locked":
                    self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "too many pairing attempts"})
                    return
                if pairing != "ok":
                    self._json(HTTPStatus.FORBIDDEN, {"error": "invalid or expired pairing code"})
                    return
                device_name = str(payload.get("device_name", "Kabin device"))[:80]
                device_token = service.config.add_paired_device(device_name)
                self._json(HTTPStatus.CREATED, {"token": device_token, "host": host_name})

            def _read_payload(self):
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length < 0:
                        raise ValueError("negative content length")
                    length = min(length, MAX_PAYLOAD_BYTES)
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
        return self.attempt_pairing(code) == "ok"

    def attempt_pairing(self, code: str) -> str:
        now = time.monotonic()
        self._pair_failures = [stamp for stamp in self._pair_failures if now - stamp < PAIR_WINDOW]
        if len(self._pair_failures) >= PAIR_MAX_FAILURES:
            return "locked"
        valid = (
            self.pairing_code is not None
            and time.monotonic() <= self.pairing_expires
            and hmac.compare_digest(_pairing_bytes(code), _pairing_bytes(self.pairing_code))
        )
        if valid:
            self.pairing_code = None
            self.pairing_expires = 0
            self._pair_failures = []
            return "ok"
        self._pair_failures.append(now)
        return "invalid"

    def _drop_sessions_locked(self, session_ids) -> list:
        """Forget these sessions; returns their helpers for the caller to
        close *outside* the lock (closing waits on a subprocess)."""
        helpers = []
        for session_id in session_ids:
            self.sessions.pop(session_id, None)
            self.session_games.pop(session_id, None)
            helper = self.session_helpers.pop(session_id, None)
            if helper:
                helpers.append(helper)
        return helpers

    def _expire_sessions_locked(self, now: float) -> list:
        """Sweep timed-out sessions, then oldest-first past MAX_SESSIONS.

        Nothing used to walk this dict - get_session only pruned the single
        id being fetched, and only if it had already expired - so a paired
        device could pile up sessions without limit just by retrying, each
        pinning a catalog item and a capabilities snapshot, and each
        negotiated one holding an open kabin-media-helper process.
        """
        expired = [
            session_id
            for session_id, session in self.sessions.items()
            if now - session["created_at"] > SESSION_TTL
        ]
        live = [session_id for session_id in self.sessions if session_id not in set(expired)]
        if len(live) > MAX_SESSIONS:
            live.sort(key=lambda session_id: self.sessions[session_id]["created_at"])
            expired.extend(live[: len(live) - MAX_SESSIONS])
        return self._drop_sessions_locked(expired)

    def prepare_session(self, game_id: str) -> dict | None:
        game = next(
            (item for item in self.catalog_provider() if item.id == game_id and item.launch),
            None,
        )
        if game is None:
            return None
        session_id = secrets.token_urlsafe(18)
        media = stream_offer(self.config)
        session = {
            "id": session_id,
            "game_id": game.id,
            "title": game.title,
            "state": "ready" if media.get("status") == "ready" else "prepared",
            "created_at": time.time(),
            "media": media,
            "capabilities": media_capabilities(),
        }
        with self.sessions_lock:
            self.sessions[session_id] = session
            self.session_games[session_id] = game
            # Swept after inserting so the cap counts this session too;
            # it's the newest, so oldest-first eviction never drops it.
            stale_helpers = self._expire_sessions_locked(time.time())
        for helper in stale_helpers:
            helper.close()
        return dict(session)

    def get_session(self, session_id: str) -> dict | None:
        stale_helpers = []
        result = None
        with self.sessions_lock:
            session = self.sessions.get(session_id)
            if session is not None:
                if time.time() - session["created_at"] > SESSION_TTL:
                    stale_helpers = self._drop_sessions_locked([session_id])
                else:
                    result = dict(session)
        for helper in stale_helpers:
            helper.close()
        return result

    def mark_media_connected(self, session_id: str) -> bool:
        with self.sessions_lock:
            session = self.sessions.get(session_id)
            if not session or time.time() - session["created_at"] > SESSION_TTL:
                return False
            session["media"]["status"] = "connected"
            session["state"] = "ready"
            return True

    def negotiate_offer(self, session_id: str, offer_sdp: str) -> str | None:
        session = self.get_session(session_id)
        if not session:
            return None
        helper = MediaHelperSession("host")
        with self.sessions_lock:
            previous = self.session_helpers.pop(session_id, None)
            self.session_helpers[session_id] = helper
        if previous:
            previous.close()
        try:
            answer = answer_host_offer(helper, offer_sdp)
            self.mark_media_connected(session_id)
            return answer
        except MediaHelperError:
            helper.close()
            with self.sessions_lock:
                self.session_helpers.pop(session_id, None)
            raise

    def activate_session(self, session_id: str) -> tuple[int, dict]:
        session = self.get_session(session_id)
        if not session:
            return HTTPStatus.NOT_FOUND, {"error": "session not found or expired"}
        media = session.get("media") or {}
        if media.get("status") != "connected":
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
            offer = stream_offer(self.config)
            if offer.get("protocol") == "kabin":
                metadata.append("streaming=kabin")
            self.publisher = subprocess.Popen(
                [executable, name, SERVICE_TYPE, str(port), *metadata],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            self.publisher = None

    def stop(self):
        with self.sessions_lock:
            helpers = list(self.session_helpers.values())
            self.session_helpers.clear()
        for helper in helpers:
            helper.close()
        if self.publisher:
            self.publisher.terminate()
            self.publisher = None
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        self.thread = None


def is_safe_artwork_file(path) -> bool:
    """Refuse symlinks so a cover named next to a ROM cannot point at arbitrary files."""
    if not path:
        return False
    candidate = Path(path)
    try:
        if candidate.is_symlink():
            return False
        resolved = candidate.resolve()
    except OSError:
        return False
    return resolved.is_file() and not resolved.is_symlink()


def artwork_file_for_item(item) -> str | None:
    icon_path = getattr(item, "icon_path", None)
    if icon_path and is_safe_artwork_file(icon_path):
        return str(icon_path)
    extra = getattr(item, "extra", None) or {}
    appid = extra.get("appid")
    if appid:
        from .icons import cached_path

        cached = cached_path(str(appid))
        if cached and is_safe_artwork_file(cached):
            return str(cached)
    return None


def media_file_for_item(item, media_dirs, track: int = 0) -> str | None:
    tracks = playable_tracks(item)
    if not tracks:
        return None
    index = max(0, min(int(track or 0), len(tracks) - 1))
    path = tracks[index]
    if not is_safe_media_file(path, media_dirs):
        return None
    return str(path)


def media_stream_url(host: dict, item_id: str, track: int = 0) -> str:
    query = f"id={urllib.parse.quote(item_id, safe='')}"
    if track:
        query += f"&track={int(track)}"
    return host_url(host, f"/v1/media/stream?{query}")


def push_remote_progress(host: dict, token: str, item_id: str, position: float, duration: float, track: int = 0, timeout=5) -> dict:
    url = host_url(host, "/v1/media/progress")
    body = json.dumps(
        {
            "id": item_id,
            "position": position,
            "duration": duration,
            "track": track,
        }
    ).encode()
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


def signal_remote_session(
    host: dict, token: str, session_id: str, offer_sdp: str, timeout=20
) -> dict:
    url = host_url(host, f"/v1/sessions/{urllib.parse.quote(session_id, safe='')}/signal")
    body = json.dumps({"type": "offer", "sdp": offer_sdp}).encode()
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
