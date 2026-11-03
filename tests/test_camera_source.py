"""입력 계약, 오류/해제 경로와 실제 60초 MP4 읽기를 검증한다."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from tools.make_sample_video import make
from walkaid.io import camera_source
from walkaid.io.camera_source import Frame, frames


class FakeCapture:
    def __init__(self, timestamps=(0.0, 100.0, 200.0), fps=10.0, opened=True):
        self.timestamps = timestamps
        self.fps = fps
        self.opened = opened
        self.index = -1
        self.released = False

    def isOpened(self):
        return self.opened

    def read(self):
        self.index += 1
        if self.index >= len(self.timestamps):
            return False, None
        return True, np.full((24, 32, 3), self.index, dtype=np.uint8)

    def get(self, prop):
        if prop == cv2.CAP_PROP_FPS:
            return self.fps
        assert prop == cv2.CAP_PROP_POS_MSEC
        return self.timestamps[self.index]

    def release(self):
        self.released = True


def install_capture(monkeypatch, capture):
    opened_sources = []

    def open_capture(source):
        opened_sources.append(source)
        return capture

    monkeypatch.setattr(camera_source.cv2, "VideoCapture", open_capture)
    return opened_sources


@pytest.mark.parametrize("source, device", [("0", 0), ("2", 2), ("clip.mp4", "clip.mp4")])
def test_sources_share_frame_contract(monkeypatch, source, device):
    capture = FakeCapture()
    opened = install_capture(monkeypatch, capture)
    clock = iter([1000.0, 1000.1, 1000.2])
    monkeypatch.setattr(camera_source.time, "time", lambda: next(clock))

    result = list(frames(source))

    assert opened == [device]
    assert len(result) == 3
    assert all(isinstance(frame, Frame) for frame in result)
    assert all(frame.image.shape == (24, 32, 3) and frame.image.dtype == np.uint8 for frame in result)
    start = 0.0 if source == "clip.mp4" else 1000.0
    assert [frame.ts for frame in result] == pytest.approx([start, start + 0.1, start + 0.2])
    assert [int(frame.image[0, 0, 0]) for frame in result] == [0, 1, 2]
    assert capture.released


@pytest.mark.parametrize("source", ["0", "clip.mp4"])
def test_max_fps_skips_frames(monkeypatch, source):
    capture = FakeCapture(tuple(i * 100.0 for i in range(11)))
    install_capture(monkeypatch, capture)
    clock = iter(i / 10 for i in range(11))
    monkeypatch.setattr(camera_source.time, "time", lambda: next(clock))

    result = list(frames(source, max_fps=5))

    assert [frame.ts for frame in result] == pytest.approx([0, 0.2, 0.4, 0.6, 0.8, 1])
    assert capture.released


@pytest.mark.parametrize("limit", [0, -1, float("inf"), float("nan")])
def test_invalid_max_fps_does_not_open_device(monkeypatch, limit):
    opened = install_capture(monkeypatch, FakeCapture())
    with pytest.raises(ValueError, match="max_fps"):
        list(frames("0", max_fps=limit))
    assert opened == []


def test_unopened_input_is_released(monkeypatch):
    capture = FakeCapture(opened=False)
    install_capture(monkeypatch, capture)
    with pytest.raises(FileNotFoundError, match="missing.mp4"):
        list(frames("missing.mp4"))
    assert capture.released


def test_early_close_releases_capture(monkeypatch):
    capture = FakeCapture()
    install_capture(monkeypatch, capture)
    stream = frames("clip.mp4")
    next(stream)
    stream.close()
    assert capture.released


def test_read_exception_releases_capture(monkeypatch):
    capture = FakeCapture()
    install_capture(monkeypatch, capture)

    def fail():
        raise RuntimeError("read failed")

    monkeypatch.setattr(capture, "read", fail)
    with pytest.raises(RuntimeError, match="read failed"):
        list(frames("clip.mp4"))
    assert capture.released


@pytest.mark.parametrize("timestamps", [(0, 0, 0), (0, float("nan"), -1), (0, 100, 50)])
def test_bad_video_timestamps_fall_back_to_fps(monkeypatch, timestamps):
    capture = FakeCapture(timestamps)
    install_capture(monkeypatch, capture)
    assert [frame.ts for frame in frames("clip.mp4")] == pytest.approx([0, 0.1, 0.2])
    assert capture.released


def test_unusable_timing_raises_and_releases(monkeypatch):
    capture = FakeCapture((0, 0), fps=0)
    install_capture(monkeypatch, capture)
    with pytest.raises(ValueError, match="FPS"):
        list(frames("clip.mp4"))
    assert capture.released


def test_reads_entire_60_second_mp4(tmp_path: Path):
    path = make(tmp_path / "minute.mp4", seconds=60, fps=10)
    count = 0
    previous_ts = -1.0
    for frame in frames(str(path)):
        assert frame.image.shape == (240, 320, 3)
        assert frame.image.dtype == np.uint8
        assert frame.ts > previous_ts
        previous_ts = frame.ts
        count += 1
    assert count == 600
    assert previous_ts == pytest.approx(59.9, abs=0.11)

    limited = list(frames(str(path), max_fps=5))
    assert len(limited) == 300
    assert limited[-1].ts == pytest.approx(59.8, abs=0.11)
