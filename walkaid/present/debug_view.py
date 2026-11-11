"""시연용 디버그 화면 (#10). 검출 박스, 신호 색, 현재 상태, fps 를 영상 위에 겹쳐 보여 준다.

표현 계층: 검출 방법은 모른다. SceneState, State, 그리고 그릴 박스 좌표(x, y, w, h)만 받는다.
박스는 SceneState 에 없으므로(#1 약속) main 이 검출기의 디버그용 `last_box` 를 넘겨 준다. 없으면 박스 없이 그린다.

cv2.putText 는 한글을 못 그리므로 화면 글자는 영어로 쓴다.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

import cv2
import numpy as np

from walkaid.logic.scene_state import SceneState
from walkaid.logic.signal_fsm import State

Box = tuple[int, int, int, int]  # (x, y, w, h)

# BGR 색
SIGNAL_COLORS: dict[str, tuple[int, int, int]] = {
    "red": (0, 0, 255),
    "green": (0, 200, 0),
    "off": (160, 160, 160),
    "unknown": (0, 200, 255),  # 주황: 확신 없음
}
STATE_COLORS: dict[State, tuple[int, int, int]] = {
    State.NO_SIGNAL: (90, 90, 90),
    State.WAIT: (0, 0, 200),
    State.CROSS: (0, 170, 0),
    State.BLINK: (0, 200, 220),
    State.UNKNOWN: (130, 0, 130),
}
WINDOW = "walkaid debug"


class FpsMeter:
    """최근 window 프레임의 처리 속도(초당 프레임 수)."""

    def __init__(self, window: int = 10, clock: Callable[[], float] = time.monotonic) -> None:
        self._times: deque[float] = deque(maxlen=window)
        self._clock = clock

    def tick(self) -> float:
        self._times.append(self._clock())
        if len(self._times) < 2:
            return 0.0
        span = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / span if span > 0 else 0.0


def render(image: np.ndarray, scene: SceneState, state: State, box: Box | None = None, fps: float = 0.0) -> np.ndarray:
    """원본은 그대로 두고, 정보를 겹쳐 그린 새 이미지를 돌려준다."""
    out = image.copy()
    h, w = out.shape[:2]
    sig = scene.signal

    # 1) 검출 박스 + 신호 색
    if box is not None:
        x, y, bw, bh = box
        color = SIGNAL_COLORS.get(sig.color, SIGNAL_COLORS["unknown"])
        cv2.rectangle(out, (x, y), (x + bw, y + bh), color, 2)
        label = f"{sig.color} {sig.conf:.2f}" + ("" if sig.pos_check else " pos?")
        cv2.putText(out, label, (x, max(15, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # 2) 위쪽 띠: 현재 상태 (상태마다 다른 색)
    band = max(30, h // 12)
    cv2.rectangle(out, (0, 0), (w, band), STATE_COLORS[state], -1)
    cv2.putText(out, state.value, (10, int(band * 0.72)), cv2.FONT_HERSHEY_SIMPLEX, band / 45, (255, 255, 255), 2)
    cv2.putText(out, f"{fps:4.1f} fps", (w - 120, int(band * 0.72)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # 3) 아래쪽 한 줄: 프레임 상태, 신호, 점자블록
    paving = scene.paving
    info = (
        f"t={scene.ts:.2f}s  frame_ok={scene.frame_ok}  "
        f"signal={sig.color if sig.present else 'none'}  "
        f"paving={paving.offset if paving.present else 'none'}"
    )
    cv2.rectangle(out, (0, h - 24), (w, h), (0, 0, 0), -1)
    cv2.putText(out, info, (8, h - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    return out


class DebugView:
    """창에 띄운다. 영상 파일은 영상 안의 시각에 맞춰 천천히 보여 준다(파일은 실제보다 빨리 읽히기 때문)."""

    def __init__(self, realtime: bool = True) -> None:
        self.fps = FpsMeter()
        self.realtime = realtime
        self._start: tuple[float, float] | None = None  # (첫 프레임 ts, 그때 컴퓨터 시각)

    def show(self, image: np.ndarray, scene: SceneState, state: State, box: Box | None = None) -> bool:
        """한 프레임을 그린다. 사용자가 q 또는 Esc 를 누르면 False."""
        if self.realtime:
            self._wait_for(scene.ts)
        cv2.imshow(WINDOW, render(image, scene, state, box, self.fps.tick()))
        return cv2.waitKey(1) & 0xFF not in (ord("q"), 27)

    def _wait_for(self, ts: float) -> None:
        now = time.monotonic()
        if self._start is None:
            self._start = (ts, now)
            return
        delay = self._start[1] + (ts - self._start[0]) - now
        if delay > 0:
            time.sleep(min(delay, 1.0))

    def close(self) -> None:
        cv2.destroyWindow(WINDOW)
