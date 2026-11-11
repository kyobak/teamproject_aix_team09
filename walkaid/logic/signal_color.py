"""보행 신호등 박스 → 켜진 불의 색 (#6). 안전 파일 — 변경 시 safety 라벨 + 2명 승인.

입력: 신호등 몸체 전체를 잘라 낸 BGR 이미지. 실제 거리의 보행 신호등은 세로 3칸이다.
    맨 위 = 빨간 사람, 가운데 = 초록 사람, 맨 아래 = 남은 시간 숫자(초록)
출력: classify() → (color, conf, pos_check) / classify_signal() → SignalInfo(present=True, ...)

판단
- 칸을 위·가운데·아래 3등분한다. 숫자 칸(아래)은 색 판단에 쓰지 않는다
  (숫자만 켜진 순간 = 초록 사람이 꺼진 점멸 순간 → off. 숫자를 초록으로 읽으면 점멸을 놓친다)
- 켜진 불 = 아주 밝은 픽셀(가운데가 하얗게 날아가도 잡힘) + 그 주변 색(빨강 계열 / 청록 계열)
- 빨강은 위 칸, 초록은 가운데 칸에서만 인정 (pos_check). 어긋나거나 둘 다 켜졌거나 애매하면 unknown
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from walkaid.logic.scene_state import SignalColor, SignalInfo

_DEFAULTS = {
    "min_conf": 0.8,
    "min_side_px": 8,  # 짧은 변이 이보다 작으면 판단하지 않음 (라벨링 가이드와 같음)
    "lit_v": 200,  # 켜진 불로 볼 밝기 (가운데가 하얗게 날아가도 이 이상)
    "color_s": 60,  # 색이 있다고 볼 채도
    "color_v": 100,  # 색을 볼 최소 밝기
    "lit_frac": 0.06,  # 칸 넓이 대비 켜진 픽셀 비율이 이 이상이면 '켜짐'
    "washout_ratio": 0.4,  # 위·가운데 칸에서 색 없이 하얀 픽셀이 이 비율 이상이면 역광으로 날아감 → unknown
}
# 색상(H, 0~179) 계열. 빨간 LED 둘레는 진한 빨강~자홍 (주황·노랑 단풍과 겹치지 않게 12 까지만)
_RED_H = ((0, 12), (155, 179))
_GREEN_H = ((65, 100),)  # 한국 보행 신호 초록은 청록에 가깝다 (H 80~90)


@dataclass
class LampStats:
    """칸별 '켜진 빛' 비율 (0~1). 빛 = 색 픽셀 + 그 색 바로 옆의 하얗게 날아간 픽셀. 튜닝·디버그 화면용."""

    red_top: float  # 위 칸의 빨간 빛 (정상 위치)
    green_mid: float  # 가운데 칸의 초록 빛 (정상 위치)
    green_top: float  # 위 칸의 초록 빛 (번짐 또는 위치 어긋남)
    red_mid: float  # 가운데 칸의 빨간 빛 (번짐 또는 위치 어긋남)
    green_bottom: float  # 숫자 칸의 초록 빛 (색 판단에는 안 씀)
    white: float  # 위·가운데 칸에서 색 없이 하얗게 날아간 픽셀 비율 (역광)


def _params(config: dict) -> dict:
    p = dict(_DEFAULTS)
    p.update((config or {}).get("signal", {}) or {})
    return p


def _hue_in(h: np.ndarray, ranges) -> np.ndarray:
    m = np.zeros(h.shape, bool)
    for lo, hi in ranges:
        m |= (h >= lo) & (h <= hi)
    return m


def lamp_masks(hsv: np.ndarray, p: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(켜진 픽셀, 빨강 계열 색 픽셀, 청록 계열 색 픽셀) 마스크."""
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    lit = v >= p["lit_v"]
    colored = (s >= p["color_s"]) & (v >= p["color_v"])
    return lit, colored & _hue_in(h, _RED_H), colored & _hue_in(h, _GREEN_H)


def _glow(lit: np.ndarray, color: np.ndarray) -> np.ndarray:
    """색 픽셀 + 그 색에 둘러싸인 하얗게 날아간 픽셀 (LED 가운데)."""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    near = cv2.dilate(color.astype(np.uint8), k) > 0
    return color | (lit & near)


def measure(crop: np.ndarray, config: dict) -> LampStats:
    p = _params(config)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    lit, red, green = lamp_masks(hsv, p)
    red_glow, green_glow = _glow(lit, red), _glow(lit, green)
    hgt = hsv.shape[0]
    top, mid, bot = slice(0, hgt // 3), slice(hgt // 3, 2 * hgt // 3), slice(2 * hgt // 3, hgt)

    def frac(mask, rows):
        part = mask[rows]
        return float(part.mean()) if part.size else 0.0

    return LampStats(
        red_top=frac(red_glow, top),
        green_mid=frac(green_glow, mid),
        green_top=frac(green_glow, top),
        red_mid=frac(red_glow, mid),
        green_bottom=frac(green_glow, bot),
        white=frac(lit & ~red_glow & ~green_glow, slice(0, 2 * hgt // 3)),
    )


Result = tuple[SignalColor, float, bool]  # (color, conf, pos_check)
_UNKNOWN: Result = ("unknown", 0.0, False)


def classify(crop: np.ndarray | None, config: dict) -> Result:
    """신호등 몸체(3칸)만 잘라낸 이미지 한 장 → (color, conf, pos_check). 확실하지 않으면 항상 unknown."""
    p = _params(config)
    if crop is None or crop.ndim != 3 or crop.shape[2] != 3:
        return _UNKNOWN
    if min(crop.shape[:2]) < p["min_side_px"]:
        return _UNKNOWN

    s = measure(crop, config)
    if s.white >= p["washout_ratio"]:
        return _UNKNOWN  # 역광으로 하얗게 날아감 → 색을 볼 수 없다 (off 로 내면 점멸로 오해할 수 있다)
    lf = p["lit_frac"]
    # 숫자 칸 빛이 가운데 칸으로 번진 것은 초록 사람이 아니다: 가운데 빛이 숫자 칸 빛의 절반도 안 되면 번짐으로 본다
    spill = s.green_mid < 0.5 * s.green_bottom
    red_on, green_on = s.red_top >= lf, s.green_mid >= lf and not spill
    if red_on and green_on:
        return _UNKNOWN  # 빨강·초록 칸이 동시에 켜짐 → 믿지 않는다
    if red_on:
        conf = s.red_top / (s.red_top + s.green_top + s.red_mid)  # 빨간 빛이 위 칸에 모여 있을수록 높다
        return ("red", round(conf, 3), True) if conf >= p["min_conf"] else _UNKNOWN
    if green_on:
        conf = s.green_mid / (s.green_mid + s.red_mid + s.red_top)
        return ("green", round(conf, 3), True) if conf >= p["min_conf"] else _UNKNOWN
    # 위·가운데 모두 정상 위치 빛이 없다. 엉뚱한 칸에 빛이 있으면(위 칸 초록, 가운데 빨강) 위치 어긋남
    stray = max(s.green_top, s.red_mid, s.red_top, 0.0 if spill else s.green_mid)
    conf = 1.0 - stray / lf
    return ("off", round(conf, 3), False) if conf >= p["min_conf"] else _UNKNOWN


def classify_signal(crop: np.ndarray | None, config: dict) -> SignalInfo:
    """classify() 결과를 SceneState.signal 에 바로 넣을 수 있는 SignalInfo 로 감싼다."""
    color, conf, pos_check = classify(crop, config)
    return SignalInfo(present=True, color=color, conf=conf, pos_check=pos_check)
