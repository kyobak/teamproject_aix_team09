"""HTTPS camera frame endpoint for the phone demo (#44)."""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import ssl
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import unquote, urlsplit

import cv2
import numpy as np

from walkaid.io.config import load_config
from walkaid.logic.detector import make_detector
from walkaid.logic.scene_state import SceneState
from walkaid.logic.signal_fsm import SignalFSM, State

MAX_JPEG_BYTES = 2 * 1024 * 1024
SESSION_HEADER = "X-Walkaid-Session"
SESSION_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")


class FrameError(Exception):
    def __init__(self, status: HTTPStatus, reason: str) -> None:
        super().__init__(reason)
        self.status = status


class FramePipeline:
    """One live stream at a time; avoid carrying a transition between cameras."""

    def __init__(self, detector_name: str, config: dict, clock=time.perf_counter) -> None:
        self.detector_name = detector_name
        self.config = config
        self.clock = clock
        self.detector = make_detector(detector_name, config)
        self.fsm = SignalFSM(config)
        self.frame_gap = self.fsm.p["frame_gap_sec"]
        self.session: str | None = None
        self.last_frame_at: float | None = None
        self.state_lock = Lock()
        self.processing = Lock()

    def _expire(self, now: float) -> None:
        if self.last_frame_at is not None and now - self.last_frame_at > self.frame_gap:
            self.fsm.update(SceneState(ts=now, frame_ok=False))
            self.last_frame_at = None

    def expire(self) -> None:
        with self.state_lock:
            self._expire(self.clock())

    def status(self, session: str) -> State:
        with self.state_lock:
            self._expire(self.clock())
            return self.fsm.state if self.session == session else State.UNKNOWN

    def submit(self, session: str, received_at: float, jpeg: bytes) -> State:
        if not self.processing.acquire(blocking=False):
            raise FrameError(HTTPStatus.CONFLICT, "frame processing busy")
        try:
            with self.state_lock:
                now = self.clock()
                self._expire(now)
                if self.last_frame_at is not None and self.session != session:
                    raise FrameError(HTTPStatus.CONFLICT, "another camera session is active")
                if self.last_frame_at is not None and received_at < self.last_frame_at:
                    raise FrameError(HTTPStatus.CONFLICT, "out-of-order frame")
                if now - received_at > self.frame_gap:
                    return State.UNKNOWN

            if not jpeg.startswith(b"\xff\xd8\xff"):
                raise FrameError(HTTPStatus.BAD_REQUEST, "invalid JPEG")
            try:
                image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            except cv2.error as exc:
                raise FrameError(HTTPStatus.BAD_REQUEST, "invalid JPEG") from exc
            if image is None:
                raise FrameError(HTTPStatus.BAD_REQUEST, "invalid JPEG")
            if image.shape[0] * image.shape[1] > 4_000_000:
                raise FrameError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "image exceeds four megapixels")

            if self.session is not None and self.session != session:
                self.detector = make_detector(self.detector_name, self.config)
            scene = self.detector.detect(image, received_at)

            with self.state_lock:
                now = self.clock()
                self._expire(now)
                if now - received_at > self.frame_gap:
                    self.fsm.update(SceneState(ts=now, frame_ok=False))
                    self.last_frame_at = None
                    return State.UNKNOWN
                self.session = session
                self.last_frame_at = received_at
                return self.fsm.update(scene)
        finally:
            self.processing.release()


class FrameServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], pipeline: FramePipeline, web_dir: Path | None = None) -> None:
        self.pipeline = pipeline
        self.web_dir = web_dir.resolve() if web_dir is not None else None
        super().__init__(address, FrameHandler)

    def service_actions(self) -> None:
        self.pipeline.expire()


class FrameHandler(BaseHTTPRequestHandler):
    server: FrameServer
    timeout = 2.0

    def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, state: State, **fields: str) -> None:
        body = json.dumps({"state": state.value, **fields}).encode("utf-8")
        self._send(status, "application/json; charset=utf-8", body)

    def _session(self) -> str:
        session = self.headers.get(SESSION_HEADER, "")
        if not SESSION_PATTERN.fullmatch(session):
            raise FrameError(HTTPStatus.BAD_REQUEST, f"missing or invalid {SESSION_HEADER}")
        return session

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/status":
            try:
                self._json(HTTPStatus.OK, self.server.pipeline.status(self._session()))
            except FrameError as exc:
                self._json(exc.status, State.UNKNOWN, error=str(exc))
            return

        web_dir = self.server.web_dir
        if web_dir is not None and not path.startswith("/api/"):
            candidate = (web_dir / (unquote(path).lstrip("/") or "index.html")).resolve()
            if candidate.is_relative_to(web_dir) and candidate.is_file():
                content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
                self._send(HTTPStatus.OK, content_type, candidate.read_bytes())
                return
        self._json(HTTPStatus.NOT_FOUND, State.UNKNOWN, error="not found")

    def do_POST(self) -> None:
        received_at = self.server.pipeline.clock()
        try:
            if urlsplit(self.path).path != "/api/frame":
                raise FrameError(HTTPStatus.NOT_FOUND, "not found")
            session = self._session()
            if self.headers.get_content_type() != "image/jpeg":
                raise FrameError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "expected image/jpeg")
            if self.headers.get("Transfer-Encoding"):
                raise FrameError(HTTPStatus.BAD_REQUEST, "expected a fixed-length JPEG body")
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,10}", lengths[0]):
                raise FrameError(HTTPStatus.LENGTH_REQUIRED, "expected one valid Content-Length")
            size = int(lengths[0])
            if not 0 < size <= MAX_JPEG_BYTES:
                raise FrameError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "JPEG size must be between 1 byte and 2 MiB")
            jpeg = self.rfile.read(size)
            if len(jpeg) != size:
                raise FrameError(HTTPStatus.BAD_REQUEST, "incomplete JPEG body")
            result = self.server.pipeline.submit(session, received_at, jpeg)
        except FrameError as exc:
            self._json(exc.status, State.UNKNOWN, error=str(exc))
        except TimeoutError:
            self._json(HTTPStatus.REQUEST_TIMEOUT, State.UNKNOWN, error="request timed out")
        else:
            self._json(HTTPStatus.OK, result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--detector", choices=["d0", "d1", "d2"], default="d0")
    parser.add_argument("--cert", required=True, type=Path, help="TLS certificate PEM")
    parser.add_argument("--key", required=True, type=Path, help="TLS private key PEM")
    parser.add_argument("--web-dir", type=Path, help="serve the #45 web app from this directory")
    args = parser.parse_args()
    if args.web_dir is not None and not args.web_dir.is_dir():
        parser.error("--web-dir must point to a directory")
    try:
        pipeline = FramePipeline(args.detector, load_config())
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(args.cert, args.key)
        # Warm the model before listening; the first phone frame has the same deadline as later frames.
        pipeline.detector.detect(np.full((480, 640, 3), 80, dtype=np.uint8), pipeline.clock())
    except (ValueError, FileNotFoundError, ssl.SSLError) as exc:
        parser.error(str(exc))
    with FrameServer((args.host, args.port), pipeline, args.web_dir) as server:
        server.socket = ctx.wrap_socket(server.socket, server_side=True, do_handshake_on_connect=False)
        print(f"Frame server: https://{args.host}:{server.server_port} ({args.detector})", flush=True)
        try:
            server.serve_forever(poll_interval=0.1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
