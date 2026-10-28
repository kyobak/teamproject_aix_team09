"""D0 — OpenCV 규칙 기반 검출기 (#5 에서 구현).

지금은 뼈대만 있다: 항상 '신호등 없음'을 돌려준다. 파이프라인이 끝까지 도는지 확인용.
"""

from __future__ import annotations

import numpy as np

from walkaid.logic.detector.base import Detector
from walkaid.logic.scene_state import SceneState


class OpenCVRuleDetector(Detector):
    def __init__(self, config: dict) -> None:
        self.config = config

    def detect(self, image: np.ndarray, ts: float) -> SceneState:
        # TODO(#5): ROI → HSV 마스크 → 컨투어 → 신호등 후보 → signal_color(#6)
        return SceneState(ts=ts)
