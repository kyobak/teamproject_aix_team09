import json
import threading
from http import HTTPStatus
from http.client import HTTPConnection

import cv2
import numpy as np
import pytest

from walkaid.frame_server import SESSION_HEADER, FramePipeline, FrameServer
from walkaid.logic.scene_state import SceneState, SignalInfo
from walkaid.logic.signal_fsm import State


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


class TestDetector:
    __test__ = False

    def detect(self, image, ts):
        color = "red" if image[0, 0, 2] > image[0, 0, 1] else "green"
        return SceneState(ts=ts, signal=SignalInfo(present=True, color=color, pos_check=True))


def make_jpeg(bgr):
    pixels = np.full((32, 32, 3), bgr, dtype=np.uint8)
    ok, jpg = cv2.imencode(".jpg", pixels)
    assert ok
    return jpg.tobytes()


def request(server, method, path, session="phone", body=None, content_type=None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    headers = {SESSION_HEADER: session}
    if content_type:
        headers["Content-Type"] = content_type
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


@pytest.fixture
def frame_server(monkeypatch):
    monkeypatch.setattr("walkaid.frame_server.make_detector", lambda name, config: TestDetector())
    clock = Clock()
    with FrameServer(("127.0.0.1", 0), FramePipeline("d0", {}, clock=clock)) as server:
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        worker.start()
        try:
            yield server, clock
        finally:
            server.shutdown()
            worker.join(timeout=3)


def test_phone_stream_expires_and_requires_a_new_red(frame_server):
    server, clock = frame_server
    assert request(server, "GET", "/api/status") == (HTTPStatus.OK, {"state": State.UNKNOWN})

    def send(bgr):
        clock.now += 0.1
        return request(server, "POST", "/api/frame", body=make_jpeg(bgr), content_type="image/jpeg")

    for _ in range(3):
        result = send((0, 0, 255))
    assert result == (HTTPStatus.OK, {"state": State.WAIT})
    for _ in range(3):
        result = send((0, 255, 0))
    assert result == (HTTPStatus.OK, {"state": State.CROSS})
    assert request(server, "GET", "/api/status", session="other") == (HTTPStatus.OK, {"state": State.UNKNOWN})
    status, payload = request(
        server, "POST", "/api/frame", session="other", body=make_jpeg((0, 255, 0)), content_type="image/jpeg"
    )
    assert status == HTTPStatus.CONFLICT and payload["state"] == State.UNKNOWN

    clock.now += 1.01
    assert request(server, "GET", "/api/status") == (HTTPStatus.OK, {"state": State.UNKNOWN})
    for _ in range(3):
        result = send((0, 255, 0))
    assert result == (HTTPStatus.OK, {"state": State.UNKNOWN})


def test_invalid_jpeg_is_rejected(frame_server):
    server, _ = frame_server
    status, payload = request(server, "POST", "/api/frame", body=b"not a JPEG", content_type="image/jpeg")
    assert status == HTTPStatus.BAD_REQUEST
    assert payload == {"state": State.UNKNOWN, "error": "invalid JPEG"}
    status, payload = request(server, "POST", "/api/frame", body=make_jpeg((0, 0, 255)), content_type="image/png")
    assert status == HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    assert payload["state"] == State.UNKNOWN
