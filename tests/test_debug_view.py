"""시연용 디버그 화면 테스트 (#10).

완료 조건: 시연 화면에 검출 박스, 색, 현재 상태, fps 가 실시간으로 보인다.
CI 에는 화면이 없으므로 창을 띄우지 않고, 그린 이미지(render)와 main 연결만 확인한다.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from tools.make_sample_video import make
from walkaid import main
from walkaid.logic.scene_state import SceneState, SignalInfo
from walkaid.logic.signal_fsm import State
from walkaid.present.debug_view import SIGNAL_COLORS, STATE_COLORS, FpsMeter, render

GREEN = SceneState(ts=1.0, signal=SignalInfo(present=True, color="green", conf=0.9, pos_check=True))


def blank(h: int = 240, w: int = 320) -> np.ndarray:
    return np.zeros((h, w, 3), np.uint8)


def test_render_keeps_original_and_size():
    image = blank()
    out = render(image, GREEN, State.CROSS, box=(100, 80, 30, 90), fps=5.0)
    assert out.shape == image.shape
    assert not image.any()  # 원본은 건드리지 않는다


def test_box_is_drawn_in_signal_color():
    out = render(blank(), GREEN, State.CROSS, box=(100, 80, 30, 90))
    assert tuple(out[150, 100]) == SIGNAL_COLORS["green"]  # 박스 왼쪽 변


def test_no_box_still_shows_state():
    out = render(blank(), SceneState(ts=0.0), State.NO_SIGNAL, box=None)
    assert out[150, 160].sum() == 0  # 가운데는 그대로
    assert tuple(out[2, 2]) == STATE_COLORS[State.NO_SIGNAL]  # 위쪽 상태 띠


def test_each_state_has_distinct_band_color():
    assert set(STATE_COLORS) == set(State)
    assert len(set(STATE_COLORS.values())) == len(State)
    for state in State:
        assert tuple(render(blank(), SceneState(ts=0.0), state)[2, 2]) == STATE_COLORS[state]


def test_render_handles_unusable_frame_and_box_outside():
    scene = SceneState(ts=0.0, frame_ok=False)
    out = render(blank(), scene, State.UNKNOWN, box=(300, 200, 100, 100))  # 화면 밖으로 삐져나간 박스
    assert out.shape == (240, 320, 3)


def test_fps_meter():
    t = iter([0.0, 0.2, 0.4, 0.6, 0.8])
    meter = FpsMeter(clock=lambda: next(t))
    assert meter.tick() == 0.0  # 한 프레임으로는 알 수 없음
    for _ in range(4):
        fps = meter.tick()
    assert abs(fps - 5.0) < 1e-6


class FakeView:
    def __init__(self, stop_after: int | None = None) -> None:
        self.shown: list[tuple[State, object]] = []
        self.closed = False
        self.stop_after = stop_after

    def show(self, image, scene, state, box=None) -> bool:
        self.shown.append((state, box))
        return self.stop_after is None or len(self.shown) < self.stop_after

    def close(self) -> None:
        self.closed = True


def test_main_view_shows_every_frame_and_closes(tmp_path: Path, monkeypatch):
    view = FakeView()
    monkeypatch.setattr(main, "DebugView", lambda: view)
    said = main.run(str(make(tmp_path / "s.mp4")), view=True, max_frames=5, realtime=False)
    assert said == ["신호등이 보이지 않습니다"]  # 화면을 켜도 안내는 그대로
    assert len(view.shown) == 5
    assert view.closed


def test_main_view_stops_when_user_quits(tmp_path: Path, monkeypatch):
    view = FakeView(stop_after=2)
    monkeypatch.setattr(main, "DebugView", lambda: view)
    main.run(str(make(tmp_path / "s.mp4")), view=True, realtime=False)
    assert len(view.shown) == 2
    assert view.closed


def test_main_view_plays_video_file_in_realtime(tmp_path: Path, monkeypatch):
    """시연 화면을 켜면 영상 파일도 실제 속도로 지나간다 (#34 의 재생 방식을 그대로 씀)."""
    view = FakeView()
    monkeypatch.setattr(main, "DebugView", lambda: view)
    t0 = time.monotonic()
    main.run(str(make(tmp_path / "s.mp4")), view=True, max_frames=6)  # 5fps 로 6장 = 영상 속 1.0초
    assert time.monotonic() - t0 >= 0.9  # 처리만 하면 0.1초도 안 걸림
    assert len(view.shown) == 6
