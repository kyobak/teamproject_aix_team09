"""D1: COCO 사전학습 YOLO 위치 검출 + 기존 HSV 색 판정 (#12)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from walkaid.logic.detector.base import Detector
from walkaid.logic.scene_state import SceneState, SignalInfo
from walkaid.logic.signal_color import classify_signal

_ROOT = Path(__file__).resolve().parents[3]
_DEFAULTS = {
    "weights": "models/yolo11n.pt",
    "conf": 0.25,
    "imgsz": 640,
    "device": "cpu",
    "roi_height": 0.65,
}


def _load_model(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"D1 모델이 없습니다: {path}. docs/d1.md의 다운로드 명령을 실행하세요.")
    try:
        from ultralytics import YOLO
    except ImportError as error:
        raise RuntimeError("D1은 python -m pip install -r requirements-yolo.txt로 설치하세요.") from error
    return YOLO(str(path))


@dataclass
class _Candidate:
    box: tuple[int, int, int, int]
    signal: SignalInfo

    @property
    def area(self) -> int:
        return self.box[2] * self.box[3]


class YOLODetector(Detector):
    """보행 신호 후보를 고르며 모호한 후보나 갑작스러운 대상 변경은 unknown."""

    def __init__(self, config: dict, *, model=None) -> None:
        self.config = config
        self.p = {**_DEFAULTS, **(config.get("d1", {}) or {})}
        if not 0 < self.p["conf"] <= 1 or not 0 < self.p["roi_height"] <= 1:
            raise ValueError("D1 conf와 roi_height는 0보다 크고 1 이하여야 합니다.")
        if not isinstance(self.p["imgsz"], int) or self.p["imgsz"] <= 0:
            raise ValueError("D1 imgsz는 양의 정수여야 합니다.")
        path = Path(self.p["weights"])
        self.model = model if model is not None else _load_model(path if path.is_absolute() else _ROOT / path)
        names = self.model.names
        items = names.items() if isinstance(names, dict) else enumerate(names)
        ids = [int(key) for key, value in items if value == "traffic light"]
        if len(ids) != 1:
            raise ValueError("D1에는 traffic light 클래스가 있는 COCO 검출 모델이 필요합니다.")
        self.class_id = ids[0]
        self.last_box: tuple[int, int, int, int] | None = None
        self._target: tuple[int, int, int, int] | None = None
        self._last_seen = -math.inf

    def detect(self, image: np.ndarray, ts: float) -> SceneState:
        self.last_box = None
        if (
            image is None
            or image.ndim != 3
            or image.shape[2] != 3
            or image.dtype != np.uint8
            or image.size == 0
            or float(image.mean()) < 2.0
        ):
            self._target = None
            return SceneState(ts=ts, frame_ok=False)
        height, width = image.shape[:2]
        roi_height = max(1, int(height * self.p["roi_height"]))
        results = self.model.predict(
            source=image[:roi_height],
            classes=[self.class_id],
            conf=self.p["conf"],
            imgsz=self.p["imgsz"],
            device=self.p["device"],
            verbose=False,
            save=False,
        )
        if not results or results[0].boxes is None:
            return SceneState(ts=ts)
        boxes = results[0].boxes
        candidates = []
        for coords, score, cls in zip(
            boxes.xyxy.cpu().numpy(), boxes.conf.cpu().numpy(), boxes.cls.cpu().numpy(), strict=True
        ):
            if not np.isfinite([*coords, score, cls]).all() or cls != self.class_id or score < self.p["conf"]:
                continue
            left, top = max(0, math.floor(coords[0])), max(0, math.floor(coords[1]))
            right, bottom = min(width, math.ceil(coords[2])), min(roi_height, math.ceil(coords[3]))
            w, h = right - left, bottom - top
            # 가로 차량 신호등과 너무 작은 후보 제외. 세로 차량 신호등까지 구분하는 모델은 아니다.
            if min(w, h) < 8 or not 1.8 <= h / w <= 4.5:
                continue
            signal = classify_signal(image[top:bottom, left:right], self.config)
            candidates.append(_Candidate((left, top, w, h), signal))
        if not candidates:
            return SceneState(ts=ts)
        if self._target is not None and 0 <= ts - self._last_seen <= 2.5:
            x, y, w, h = self._target
            # 이전 몸체 폭의 0.6배 안에서만 재검출: 빨강 뒤 옆 초록 신호로 튀는 것 억제.
            candidates = [
                c
                for c in candidates
                if math.hypot(c.box[0] + c.box[2] / 2 - x - w / 2, c.box[1] + c.box[3] / 2 - y - h / 2) <= 0.6 * w
            ]
            if not candidates:
                return SceneState(ts=ts, signal=SignalInfo(present=True))
        best = max(candidates, key=lambda candidate: candidate.area)
        strong = [c for c in candidates if c.area >= best.area * 0.75]
        if len({c.signal.color for c in strong}) > 1:
            return SceneState(ts=ts, signal=SignalInfo(present=True))
        self.last_box = best.box
        self._target, self._last_seen = best.box, ts
        return SceneState(ts=ts, signal=best.signal)
