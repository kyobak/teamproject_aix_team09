"""신호 상태 머신 (#7 에서 구현). 안전 파일 — 변경 시 2명 승인.

상태: NO_SIGNAL, WAIT, CROSS, BLINK, UNKNOWN
원칙: 확실하지 않으면 CROSS 를 내지 않는다.
"""

from __future__ import annotations

from enum import StrEnum

from walkaid.logic.scene_state import SceneState


class State(StrEnum):
    NO_SIGNAL = "NO_SIGNAL"
    WAIT = "WAIT"
    CROSS = "CROSS"
    BLINK = "BLINK"
    UNKNOWN = "UNKNOWN"


class SignalFSM:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.state = State.UNKNOWN

    def update(self, scene: SceneState) -> State:
        # TODO(#7): 연속 프레임 확인, 점멸 감지, '직전 WAIT' 조건, 프레임 끊김 처리
        if not scene.frame_ok:
            self.state = State.UNKNOWN
        elif not scene.signal.present:
            self.state = State.NO_SIGNAL
        else:
            self.state = State.UNKNOWN  # 구현 전에는 절대 CROSS 를 내지 않는다
        return self.state
