"""SceneState — 모듈 사이의 유일한 약속 (#1 에서 docs/scene-state.md 와 함께 확정).

인식(perception)은 SceneState 를 만들고, 판단(signal_fsm)은 SceneState 만 읽는다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

SignalColor = Literal["red", "green", "off", "unknown"]
PavingType = Literal["line", "dot", "none"]
Offset = Literal["left", "center", "right", "none"]


@dataclass
class SignalInfo:
    present: bool = False
    color: SignalColor = "unknown"
    conf: float = 0.0
    pos_check: bool = False  # 색과 위치(위=빨강, 아래=초록)가 일치하는가


@dataclass
class PavingInfo:
    present: bool = False
    type: PavingType = "none"
    offset: Offset = "none"
    conf: float = 0.0


@dataclass
class SceneState:
    ts: float
    frame_ok: bool = True
    signal: SignalInfo = field(default_factory=SignalInfo)
    paving: PavingInfo = field(default_factory=PavingInfo)

    def to_dict(self) -> dict:
        return asdict(self)
