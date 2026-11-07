"""보행 신호등 박스 → 켜진 불의 색 (#6). 안전 파일 — 변경 시 safety 라벨 + 2명 승인.

입력: 신호등 몸체 전체(위·아래 두 칸)를 잘라 낸 BGR 이미지 (docs/labeling-guide.md 박스 규칙)
출력: classify() → (color, conf, pos_check) / classify_signal() → SignalInfo(present=True, ...)

판단 순서
1. 박스가 비었거나 너무 작으면 unknown
2. 박스를 위·아래로 나누고, 각 절반에서 빨강·초록 HSV 마스크 픽셀 비율을 잰다
3. 켜진 불이 없으면: 하얗게 날아간 영역이 넓으면 unknown(역광), 아니면 off
4. 켜진 불이 있으면: 더 많은 색을 고르고, 빨강은 위·초록은 아래에 있어야 pos_check
   - 위치가 어긋나면 unknown
   - conf = 색 순도 × 위치 일치도 × 밝기 충분도, min_conf 미만이면 unknown
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from walkaid.logic.scene_state import SignalColor, SignalInfo

# config.yaml 의 signal 항목이 없을 때 쓰는 값 (config.yaml 과 같은 값)
_DEFAULTS = {
    "red_ranges": [[[0, 100, 120], [10, 255, 255]], [[170, 100, 120], [179, 255, 255]]],
    "green_range": [[50, 80, 120], [95, 255, 255]],
    "min_conf": 0.8,
    # 아래 값은 #6 에서 새로 둔 시작값 — 우리 영상으로 다시 맞춘다
    "min_lit_ratio": 0.03,  # 절반 영역 중 이 비율 이상이 색으로 잡혀야 '켜짐'
    "full_lit_ratio": 0.08,  # 이 비율 이상이면 밝기 충분도 1.0
    "washout_ratio": 0.4,  # 절반 영역 중 이 비율 이상이 흰색이면 '날아감'
    "min_side_px": 8,  # 짧은 변이 이보다 작으면 판단하지 않음 (라벨링 가이드와 같음)
}
_MID_MARGIN = 0.05  # 위·아래 경계 근처 띠(높이의 5%씩)는 어느 쪽에도 세지 않는다
_WHITE_S_MAX = 60  # 채도가 이보다 낮고
_WHITE_V_MIN = 220  # 명도가 이보다 높으면 '하얗게 날아간' 픽셀


@dataclass
class LampStats:
    """위·아래 절반별 측정값 (비율 0~1). 튜닝·디버그 화면용."""

    red_top: float
    red_bottom: float
    green_top: float
    green_bottom: float
    white_top: float
    white_bottom: float


def _params(config: dict) -> dict:
    p = dict(_DEFAULTS)
    p.update((config or {}).get("signal", {}) or {})
    return p


def _in_ranges(hsv: np.ndarray, ranges: list) -> np.ndarray:
    mask = np.zeros(hsv.shape[:2], dtype=bool)
    for lo, hi in ranges:
        mask |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8)) > 0
    return mask


def measure(box_bgr: np.ndarray, config: dict) -> LampStats:
    """박스 이미지의 위·아래 절반에서 빨강·초록·흰색 픽셀 비율을 잰다."""
    p = _params(config)
    hsv = cv2.cvtColor(box_bgr, cv2.COLOR_BGR2HSV)
    red = _in_ranges(hsv, p["red_ranges"])
    green = _in_ranges(hsv, [p["green_range"]])
    white = (hsv[..., 1] < _WHITE_S_MAX) & (hsv[..., 2] > _WHITE_V_MIN)

    h = hsv.shape[0]
    top = slice(0, max(1, int(h * (0.5 - _MID_MARGIN))))
    bottom = slice(min(h - 1, int(h * (0.5 + _MID_MARGIN))), h)

    def ratio(mask: np.ndarray, rows: slice) -> float:
        part = mask[rows]
        return float(part.mean()) if part.size else 0.0

    return LampStats(
        red_top=ratio(red, top),
        red_bottom=ratio(red, bottom),
        green_top=ratio(green, top),
        green_bottom=ratio(green, bottom),
        white_top=ratio(white, top),
        white_bottom=ratio(white, bottom),
    )


Result = tuple[SignalColor, float, bool]  # (color, conf, pos_check)
_UNKNOWN: Result = ("unknown", 0.0, False)


def _unknown() -> Result:
    return _UNKNOWN


def classify(box_bgr: np.ndarray | None, config: dict) -> Result:
    """신호등 몸체 박스 한 장 → (color, conf, pos_check). 확실하지 않으면 항상 unknown."""
    p = _params(config)
    if box_bgr is None or box_bgr.ndim != 3 or box_bgr.shape[2] != 3:
        return _unknown()
    if min(box_bgr.shape[:2]) < p["min_side_px"]:
        return _unknown()

    s = measure(box_bgr, config)
    red_total = s.red_top + s.red_bottom
    green_total = s.green_top + s.green_bottom
    lit = max(s.red_top, s.red_bottom, s.green_top, s.green_bottom)

    # 켜진 불이 없음 → off, 단 하얗게 날아갔으면 색을 볼 수 없으므로 unknown
    if lit < p["min_lit_ratio"]:
        if max(s.white_top, s.white_bottom) >= p["washout_ratio"]:
            return _unknown()
        conf = 1.0 - lit / p["min_lit_ratio"]
        if conf < p["min_conf"]:
            return _unknown()
        return ("off", round(conf, 3), False)

    # 더 많이 보이는 색을 고르고, 그 색이 있어야 할 절반(빨강=위, 초록=아래)의 비율을 함께 본다
    if red_total >= green_total:
        color, dominant, other, home = "red", red_total, green_total, s.red_top
    else:
        color, dominant, other, home = "green", green_total, red_total, s.green_bottom
    position = home / dominant

    # 색과 위치가 어긋남 (빨강이 아래 / 초록이 위) → unknown
    if position < 0.5:
        return _unknown()

    purity = dominant / (dominant + other)
    strength = min(1.0, home / p["full_lit_ratio"])
    conf = purity * position * strength
    if conf < p["min_conf"]:
        return _unknown()
    return (color, round(conf, 3), True)


def classify_signal(box_bgr: np.ndarray | None, config: dict) -> SignalInfo:
    """classify() 결과를 SceneState.signal 에 바로 넣을 수 있는 SignalInfo 로 감싼다."""
    color, conf, pos_check = classify(box_bgr, config)
    return SignalInfo(present=True, color=color, conf=conf, pos_check=pos_check)
