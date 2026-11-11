"""D0 — OpenCV 규칙 기반 보행 신호등 검출기 (#5).

학습 없이 "켜진 불 + 그 둘레의 검은 세로 3칸 몸체" 라는 모양 규칙으로 신호등을 찾고,
색은 #6 classify_signal() 에 맡긴다. 정확도 목표 없이 YOLO(D1·D2)와 비교할 기준선이다.

순서
1. 화면 위쪽(roi_height)만, 작업 폭(work_width)으로 줄여서 본다
2. 켜진 불 후보: 아주 밝은 덩어리(가운데가 하얗게 날아가도 잡힘) 중 둘레가 빨강 계열 또는 청록 계열인 것
3. 불 크기로 칸 크기 S 를 정하고, 불이 몇 번째 칸인지 가정해 세로 3칸 몸체 박스를 만든다
   - 빨강 → 맨 위 칸
   - 청록 → 가운데 칸(초록 사람) 또는 맨 아래 칸(남은 시간 숫자). 위로 두 칸이 다 어두우면 숫자 칸
4. 몸체 확인: 불이 아닌 나머지 칸이 불보다 훨씬 어두워야 한다 (단풍·후미등·간판·하늘 걸러내기)
5. 통과한 후보 중 칸이 가장 큰 것 하나 (scene-state 규칙 5) → classify_signal()
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from walkaid.logic.detector.base import Detector
from walkaid.logic.scene_state import SceneState, SignalInfo
from walkaid.logic.signal_color import _params as _color_params
from walkaid.logic.signal_color import classify_signal, lamp_masks

_DEFAULTS = {
    "roi_height": 0.65,  # 화면 위에서부터 이 비율만 본다
    "work_width": 1080,  # 이 폭으로 줄여서 계산
    "min_lamp_px": 30,  # 켜진 불 덩어리 최소 넓이 (작업 크기 픽셀)
    "max_cell_frac": 0.05,  # 칸 크기 S 최대 (작업 폭 대비) — 건너편 10m 이상 신호등은 이보다 작다. 큰 빛은 간판·조명
    "min_color_frac": 0.15,  # 불 둘레에서 빨강/청록 색 픽셀 최소 비율
    "dark_ratio": 0.55,  # 꺼진 칸 밝기(중앙값)가 불 밝기의 이 비율 이하
    "dark_v_max": 120,  # 꺼진 칸 밝기 중앙값 상한
    "lamp_v_min": 190,  # 켜진 불 밝기 중앙값 하한 (LED 는 거의 최대 밝기)
    "contrast_min": 110,  # 켜진 불 밝기 - 꺼진 칸 밝기
    "rim_sat_min": 100,  # 불 둘레 색 채도 하한 (LED 빛은 진하다, 단풍·후미등은 덜 진하다)
    "fill_min": 0.35,  # 불 덩어리 채움 비율 하한
    "strong_ratio": 0.75,  # 점수가 최고의 이 비율 이상인 후보들끼리 색이 다르면 고르지 않는다
    "track_score": 0.55,  # 추적: 이전 몸체 모양과의 일치도 하한
    "track_max_gap": 2.5,  # 추적: 이 시간(초) 넘게 끊기면 새로 찾는다
    "track_max_miss": 3,  # 추적: 연속으로 이만큼 못 찾으면 새로 찾는다
    "reacquire_sec": 3.0,  # 추적을 놓친 뒤 이 시간 안에는 마지막 자리 근처 후보를 먼저 고른다
    "jump_frac": 0.5,  # 추적 박스가 한 프레임에 몸체 폭의 이 배 넘게 움직이면 '크게 움직임'
    "reacquire_dist": 0.6,  # 다시 찾을 때 마지막 자리에서 몸체 폭의 이 배 이내만 같은 신호등으로 본다
    "track_confirm_sec": 2.5,  # 추적: 이 시간 넘게 그 자리에서 켜진 불이 확인되지 않으면 버리고 새로 찾는다
}


@dataclass
class Candidate:
    box: tuple[int, int, int, int]  # 원본 좌표 (x, y, w, h), 3칸 몸체
    lamp: tuple[int, int, int, int]  # 원본 좌표, 켜진 불
    color: str  # red / green
    role: str  # top(빨강) / mid(초록 사람) / bottom(숫자)
    cell: float  # 칸 크기 S (작업 크기 픽셀)
    lamp_v: float
    dark_v: float  # 꺼진 칸 밝기 중앙값(가장 밝은 칸 기준)
    accepted: bool
    reason: str
    rim_sat: float = 0.0  # 불 둘레 색 픽셀의 채도 중앙값
    fill: float = 0.0  # 불 덩어리 채움 비율

    @property
    def score(self) -> float:
        # 신호등다움: 불과 꺼진 칸의 대비 × 둘레 색 진하기 × 칸 크기(가까운 것 우선, 규칙 5)
        return (self.lamp_v - self.dark_v) * self.rim_sat * self.cell**0.5


def _params_d(config: dict) -> dict:
    p = dict(_DEFAULTS)
    p.update((config or {}).get("detector", {}) or {})
    return p


def _median_v(value: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> float | None:
    h, w = value.shape
    xa, ya, xb, yb = int(max(0, x0)), int(max(0, y0)), int(min(w, x1)), int(min(h, y1))
    if xb - xa < 2 or yb - ya < 2:
        return None
    return float(np.median(value[ya:yb, xa:xb]))


def find_candidates(image: np.ndarray, config: dict) -> list[Candidate]:
    d, c = _params_d(config), _color_params(config)
    h0, w0 = image.shape[:2]
    scale = min(1.0, d["work_width"] / w0)
    roi = image[: max(1, int(h0 * d["roi_height"]))]
    if scale < 1.0:
        roi = cv2.resize(roi, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    rh, rw = hsv.shape[:2]
    value = hsv[..., 2]
    lit, red, green = lamp_masks(hsv, c)
    # 켜진 불 = 밝은 픽셀 + 밝게 빛나는 색 픽셀 (번짐 포함)
    # 하늘이 밝은 날·해질녘에는 불과 하늘이 몸체 테두리 몇 픽셀로만 떨어져 있다 → 덩어리를 일부러 붙이지 않는다.
    # 사람 모양 LED 가 조각나는 것은 색 픽셀끼리만 살짝 이어 준다.
    col = ((red | green) & (value >= 150)).astype(np.uint8) * 255
    col = cv2.morphologyEx(col, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    seed = np.maximum(col, lit.astype(np.uint8) * 255)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(seed, connectivity=8)
    max_cell = d["max_cell_frac"] * rw

    out: list[Candidate] = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < d["min_lamp_px"] or w > max_cell or h > max_cell * 1.2:
            continue
        # 둘레(박스를 30% 넓힌 곳)의 색으로 빨강/청록 결정
        pad = max(2, int(0.3 * max(w, h)))
        ya, yb, xa, xb = max(0, y - pad), min(rh, y + h + pad), max(0, x - pad), min(rw, x + w + pad)
        r_n, g_n = int(red[ya:yb, xa:xb].sum()), int(green[ya:yb, xa:xb].sum())
        tot = (yb - ya) * (xb - xa)
        if max(r_n, g_n) < d["min_color_frac"] * area or max(r_n, g_n) < 0.02 * tot:
            continue  # 색이 없는 밝은 것 (하늘·흰 벽·가로등)
        color = "red" if r_n >= g_n else "green"
        lamp_v = float(np.median(value[y : y + h, x : x + w][labels[y : y + h, x : x + w] == i]))
        cx, cy = x + w / 2, y + h / 2
        limit = min(d["dark_v_max"], d["dark_ratio"] * lamp_v)
        col = (red if color == "red" else green)[ya:yb, xa:xb]
        sat = hsv[ya:yb, xa:xb, 1][col]
        rim_sat = float(np.median(sat)) if sat.size else 0.0
        fill = float(area) / float(w * h)
        # 숫자 모양: '1' 은 아주 가늘고, 두 자리 숫자는 가운데에 세로 빈틈이 있다 (사람 모양은 한 덩어리)
        prof = (labels[y : y + h, x : x + w] == i).sum(axis=0).astype(float)
        mid_cols = prof[int(0.3 * w) : max(int(0.3 * w) + 1, int(0.7 * w))]
        gap = (
            w >= 6
            and mid_cols.min() <= 0.15 * prof.max()
            and prof[: int(0.3 * w)].max() > 0
            and prof[int(0.7 * w) :].max() > 0
        )
        digit_shape = w / h <= 0.45 or gap

        def cell_v(S: float, k: int, cx: float = cx, cy: float = cy) -> float | None:  # k 칸 아래(+)/위(-) 칸 밝기
            yc = cy + k * S
            return _median_v(value, cx - 0.3 * S, yc - 0.35 * S, cx + 0.3 * S, yc + 0.35 * S)

        def dark(S: float, k: int, limit: float = limit) -> bool:
            v = cell_v(S, k)
            return v is not None and v <= limit

        # 칸 크기 S: 불빛이 번지면 불이 칸보다 커 보이므로 몇 가지 크기로 맞춰 본다
        base = float(max(h * 1.15, w * 1.25, 6.0))
        sizes = [base, 0.8 * base, 0.65 * base]
        chosen = None
        for S in sizes:
            if color == "red":
                role = "top"
            else:
                # 두 칸 위가 '몸체'인지: 어둡고, 같은 높이의 양옆 바깥보다 확실히 어두워야 몸체 (배경 나무·밤과 구별)
                v2 = cell_v(S, -2)
                yc2 = cy - 2 * S
                sides2 = [v for v in (_median_v(value, cx - 1.3 * S, yc2 - 0.4 * S, cx - 0.8 * S, yc2 + 0.4 * S),
                                      _median_v(value, cx + 0.8 * S, yc2 - 0.4 * S, cx + 1.3 * S, yc2 + 0.4 * S))
                          if v is not None]  # fmt: skip
                bg2 = max(sides2) if sides2 else None  # 밝은 쪽 = 바깥 배경 (숫자 조각이 한쪽에 치우쳐도)
                if v2 is not None and bg2 is not None and bg2 - v2 >= 40 and v2 <= limit:
                    role = "bottom"  # 위로 두 칸 모두 몸체 → 숫자 칸
                elif v2 is not None and bg2 is not None and v2 - bg2 > -15 and bg2 > limit:
                    role = "mid"  # 두 칸 위는 바깥과 같은 밝은 배경 → 몸체 위쪽 끝 → 초록 사람 칸
                else:
                    role = "bottom" if digit_shape else "mid"  # 배경도 어두워서 구별 불가 → 모양으로
            others = {"top": (1, 2), "mid": (-1,), "bottom": (-2, -1)}[role]
            if all(dark(S, k) for k in others):
                chosen = (S, role, others)
                break
        if chosen is None:
            S, role, others = base, ("top" if color == "red" else "mid"), ((1, 2) if color == "red" else (-1,))
        else:
            S, role, others = chosen
        dv = max((cell_v(S, k) or 0.0) for k in others)
        reason = ""
        if lamp_v < d["lamp_v_min"]:
            reason = "dim"
        elif chosen is None:
            reason = "cells-not-dark"
        elif lamp_v - dv < d["contrast_min"]:
            reason = "low-contrast"
        elif rim_sat < d["rim_sat_min"]:
            reason = "pale-rim"
        elif fill < d["fill_min"]:
            reason = "sparse"
        top_y = cy - 0.5 * S - {"top": 0, "mid": 1, "bottom": 2}[role] * S
        box = (cx - 0.55 * S, top_y - 0.05 * S, 1.1 * S, 3.1 * S)
        out.append(
            Candidate(
                box=tuple(int(round(v / scale)) for v in box),  # type: ignore[arg-type]
                lamp=tuple(int(round(v / scale)) for v in (x, y, w, h)),  # type: ignore[arg-type]
                color=color,
                role=role,
                cell=S,
                lamp_v=lamp_v,
                dark_v=dv,
                accepted=reason == "",
                reason=reason,
                rim_sat=rim_sat,
                fill=fill,
            )
        )
    # 숫자 칸 후보는 바로 위에 초록 사람 후보가 있으면 버린다 (같은 신호등)
    mids = [k for k in out if k.accepted and k.role == "mid"]
    for k in out:
        if k.accepted and k.role == "mid":
            for m in mids:
                if (
                    m is not k
                    and abs(m.box[0] - k.box[0]) < 0.5 * m.box[2]
                    and 0 < k.lamp[1] - m.lamp[1] < 1.6 * m.box[3] / 3
                ):
                    k.accepted, k.reason = False, "countdown-of-other"
    return out


class OpenCVRuleDetector(Detector):
    """프레임마다 후보를 찾되, 한 번 찾은 신호등 몸체는 모양(밝기 패턴)으로 따라간다.

    따라가면 몸체 3칸의 위치를 알고 있으므로 숫자 칸·꺼진 순간(점멸)에도 같은 몸체를 보고 판단할 수 있다.
    """

    def __init__(self, config: dict) -> None:
        self.config = config
        self.p = _params_d(config)
        self.last_candidates: list[Candidate] = []  # 디버그 화면(#10)용
        self.last_box: tuple[int, int, int, int] | None = None
        self._track: tuple[int, int, int, int] | None = None
        self._tpl: np.ndarray | None = None
        self._mask: np.ndarray | None = None
        self._last_ts: float | None = None
        self._miss = 0
        self._confirmed_ts: float | None = None
        self._last_pos: tuple[float, float, float, int] | None = None  # (중심 x, 중심 y, 시각, 폭)
        self._red_rel: tuple[float, float] | None = None  # 추적 박스 기준 빨간 불 중심 위치
        self._prev: tuple[tuple[int, int, int, int], str] | None = None  # 직전 프레임 (박스, 색)
        self._cell: float | None = None  # 빨강→초록 불 간격으로 잰 실제 칸 크기

    def _calibrated_box(self, rcx: float, rcy: float) -> tuple[int, int, int, int]:
        S = self._cell
        return (int(round(rcx - 0.55 * S)), int(round(rcy - 0.55 * S)), int(round(1.1 * S)), int(round(3.1 * S)))

    def _calibrate(self, box: tuple[int, int, int, int], here: list[Candidate]) -> tuple[int, int, int, int]:
        """추적 중인 몸체의 칸 크기를 '빨간 불 → 초록 불' 간격으로 잰다.

        불빛이 번지면(해질녘·밤) 불 크기로 짐작한 칸이 실제보다 커져서, 3등분하면 숫자 칸이 초록 칸에 들어간다.
        같은 신호등에서 빨강(맨 위 칸)과 초록(가운데 칸)이 켜진 위치의 간격 = 정확한 칸 크기.
        """
        x, y, w, h = box
        reds = [c for c in here if c.role == "top"]
        greens = [c for c in here if c.role == "mid"]
        if reds:  # 빨간 불 = 맨 위 칸 → 위치 기준점
            c = max(reds, key=lambda c: c.score)
            rcx, rcy = c.lamp[0] + c.lamp[2] / 2, c.lamp[1] + c.lamp[3] / 2
            if self._cell is not None:
                box = self._calibrated_box(rcx, rcy)
            else:
                box = c.box
            self._red_rel = (rcx - box[0], rcy - box[1])
            return box
        if self._red_rel is not None:
            rcx, rcy = x + self._red_rel[0], y + self._red_rel[1]
            if self._cell is None and greens:
                c = max(greens, key=lambda c: c.score)
                gcy = c.lamp[1] + c.lamp[3] / 2
                est = h / 3.1
                if 0.4 * est <= gcy - rcy <= 1.3 * est:  # 초록 불은 빨간 불 바로 아래 칸
                    self._cell = float(gcy - rcy)
            if self._cell is not None:
                box = self._calibrated_box(rcx, rcy)
                self._red_rel = (rcx - box[0], rcy - box[1])
        return box

    def _select(self, accepted: list[Candidate], ts: float) -> Candidate | None:
        """새로 고를 신호등. None 이면 고르지 않는다 (→ unknown, '확실하지 않으면 건너라고 하지 않는다')."""
        # 1) 방금까지 따라가던 신호등이 있으면 그 자리 근처에서만 다시 찾는다 (다른 신호등으로 튀지 않게)
        if self._last_pos is not None and ts - self._last_pos[2] <= self.p["reacquire_sec"]:
            lx, ly, _, lw = self._last_pos

            def dist(c: Candidate) -> float:
                return float(np.hypot(c.box[0] + c.box[2] / 2 - lx, c.box[1] + c.box[3] / 2 - ly))

            # 바로 옆(폭의 1~2배)에 다른 신호등이 붙어 있는 경우가 있다 → '같은 자리'는 폭의 0.6배 이내만
            near = [c for c in accepted if dist(c) <= self.p["reacquire_dist"] * lw]
            if len({c.color for c in near}) > 1:
                return None  # 같은 자리 근처에 색이 다른 후보가 섞여 있으면 고르지 않음
            return min(near, key=dist) if near else None
        # 2) 처음 찾을 때: 신호등다움 점수가 가장 높은 후보 (규칙 5: 가장 크고 뚜렷한 것)
        best = max(accepted, key=lambda c: c.score)
        # 3) 점수가 비슷한 후보끼리 색이 다르면 어느 것이 내 횡단보도 신호인지 모른다 → 고르지 않음 (unknown)
        #    예: 나란히 있는 다른 방향 보행 신호등, 초록인 차량 신호등
        strong = [c for c in accepted if c.score >= self.p["strong_ratio"] * best.score]
        if len({c.color for c in strong}) > 1:
            return None
        return best

    def _follow(self, gray: np.ndarray) -> tuple[tuple[int, int, int, int], float] | None:
        if self._track is None or self._tpl is None:
            return None
        x, y, w, h = self._track
        H, W = gray.shape
        mx, my = 2 * w, h  # 찾는 범위 (손떨림·걸음)
        x0, y0, x1, y1 = (
            max(0, x - w - mx),
            max(0, y - h // 2 - my),
            min(W, x + 2 * w + mx),
            min(H, y + h + h // 2 + my),
        )
        region = gray[y0:y1, x0:x1]
        th, tw = self._tpl.shape
        if region.shape[0] < th or region.shape[1] < tw:
            return None
        r = cv2.matchTemplate(region, self._tpl, cv2.TM_CCOEFF_NORMED, mask=self._mask)
        r = np.nan_to_num(r, nan=-1.0, posinf=-1.0, neginf=-1.0)
        _, score, _, loc = cv2.minMaxLoc(r)
        return (x0 + loc[0] + w, y0 + loc[1] + h // 2, w, h), float(score)

    def _remember(self, gray: np.ndarray, box: tuple[int, int, int, int]) -> None:
        x, y, w, h = box
        H, W = gray.shape
        x0, y0, x1, y1 = x - w, y - h // 2, x + 2 * w, y + h + h // 2  # 몸체 + 둘레 (기둥·표지판까지 같이 기억)
        if x0 < 0 or y0 < 0 or x1 > W or y1 > H:
            self._track, self._tpl = None, None
            return
        self._track, self._tpl = box, gray[y0:y1, x0:x1].copy()
        # 몸체 안쪽(켜진 불이 바뀌는 곳)은 가리고 테두리·기둥·주변만 비교한다 — 불이 옮겨 가도 박스가 끌려가지 않게
        self._mask = np.full(self._tpl.shape, 255, np.uint8)
        self._mask[h // 2 + int(0.05 * h) : h // 2 + h - int(0.05 * h), w + int(0.15 * w) : 2 * w - int(0.15 * w)] = 0

    def detect(self, image: np.ndarray, ts: float) -> SceneState:
        self.last_candidates, self.last_box = [], None
        if image is None or image.ndim != 3 or image.size == 0 or float(image.mean()) < 2.0:
            self._track = None
            return SceneState(ts=ts, frame_ok=False)  # 규칙 6
        if self._last_ts is not None and ts - self._last_ts > self.p["track_max_gap"]:
            self._track = None
        self._last_ts = ts

        H, W = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        self.last_candidates = find_candidates(image, self.config)
        accepted = [c for c in self.last_candidates if c.accepted]

        def overlaps(c: Candidate, b: tuple[int, int, int, int]) -> bool:
            lx, ly = c.lamp[0] + c.lamp[2] / 2, c.lamp[1] + c.lamp[3] / 2
            return b[0] - 0.3 * b[2] <= lx <= b[0] + 1.3 * b[2] and b[1] - 0.1 * b[3] <= ly <= b[1] + 1.1 * b[3]

        box = None
        confirmed = False
        jumped = False
        followed = self._follow(gray)
        if followed and followed[1] >= self.p["track_score"]:
            box = followed[0]
            if self._prev is not None:
                pb = self._prev[0]
                jumped = (
                    abs(box[0] - pb[0]) > self.p["jump_frac"] * pb[2]
                    or abs(box[1] - pb[1]) > self.p["jump_frac"] * pb[2]
                )
            self._miss = 0
            here = [c for c in accepted if overlaps(c, box)]
            confirmed = bool(here)
            box = self._calibrate(box, here)
            # 켜진 불이 오래 확인되지 않는 추적은 엉뚱한 곳에 눌어붙은 것 → 버리고 새로 찾는다
            if not confirmed and (self._confirmed_ts is None or ts - self._confirmed_ts > self.p["track_confirm_sec"]):
                box, self._track = None, None
        elif self._track is not None:
            self._miss += 1
            if self._miss > self.p["track_max_miss"]:
                self._track = None
        undecided = False
        if box is None and accepted:
            pick = self._select(accepted, ts)
            if pick is None:
                undecided = True
            else:
                box = pick.box
                confirmed = True
                self._miss = 0
                # 새로 고른 신호등 → 이전 신호등에서 잰 칸 크기는 버리고, 빨간 불이면 기준점부터 다시 잡는다
                self._cell = None
                self._red_rel = None
                if pick.role == "top":
                    rcx, rcy = pick.lamp[0] + pick.lamp[2] / 2, pick.lamp[1] + pick.lamp[3] / 2
                    self._red_rel = (rcx - box[0], rcy - box[1])
        if box is None and (
            undecided or (self._last_pos is not None and ts - self._last_pos[2] <= self.p["reacquire_sec"])
        ):
            # 신호등은 있는데 어느 것인지/지금 상태를 확신할 수 없다
            return SceneState(ts=ts, signal=SignalInfo(present=True, color="unknown", conf=0.0, pos_check=False))

        if box is None:
            self._red_rel, self._cell = None, None
            return SceneState(ts=ts)  # 규칙 1
        x, y, w, h = box
        x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
        self.last_box = (x0, y0, x1 - x0, y1 - y0)
        signal = classify_signal(image[y0:y1, x0:x1], self.config)
        prev_color = self._prev[1] if self._prev is not None else None
        self._prev = (box, signal.color)
        if jumped and {signal.color, prev_color} == {"red", "green"}:
            # 추적 박스가 한 번에 크게 움직였는데 빨강↔초록이 바뀌었다 = 옆 신호등으로 미끄러졌을 수 있다
            # (실제 신호가 바뀔 때는 박스가 제자리에 있다) → 믿지 않고 새로 찾는다
            self._track, self._prev = None, None
            return SceneState(ts=ts, signal=SignalInfo(present=True, color="unknown", conf=0.0, pos_check=False))
        if confirmed and signal.color != "unknown":  # 켜진 불이 확인된 자리만 기억한다 (눌어붙음 방지)
            self._remember(gray, box)
            self._confirmed_ts = ts
            self._last_pos = (x + w / 2, y + h / 2, ts, w)
        return SceneState(ts=ts, signal=signal)
