"""신호 상태 머신 (#7). 안전 파일 — 변경 시 safety 라벨 + 2명 승인.

SceneState 를 한 프레임씩 받아 지금 상태 하나를 낸다.
상태: NO_SIGNAL, WAIT, CROSS, BLINK, UNKNOWN

원칙: 확실하지 않으면 CROSS 를 내지 않는다.
- 같은 색이 stable_frames 프레임 연속으로 보일 때만 상태를 바꾼다 (한 프레임 오인식 무시)
- CROSS 는 "빨간불(WAIT)을 보고 있다가 초록으로 바뀐 것"을 봤을 때만 낸다.
  도착했을 때 이미 초록이면 남은 시간을 모르므로 건너라고 하지 않는다
- 초록과 꺼짐이 번갈아 나오면 점멸(BLINK). 점멸 중에는 새로 건너라고 하지 않는다
- 프레임을 볼 수 없거나(frame_ok=false) 끊기면 UNKNOWN
- CROSS 중 초록이 cross_hold_sec 넘게 안 보이면 UNKNOWN (빨강이 unknown 으로 나와도 CROSS 가 남지 않게)

관찰로 세는 것 (docs/scene-state.md "상태 머신이 다시 확인하는 것")
- red·green 은 pos_check=true 일 때만, off 는 present=true 일 때만
- unknown 은 관찰로 세지 않는다. 대신 이어지던 연속 횟수를 끊는다
"""

from __future__ import annotations

from collections import deque
from enum import StrEnum

from walkaid.logic.scene_state import SceneState


class State(StrEnum):
    NO_SIGNAL = "NO_SIGNAL"
    WAIT = "WAIT"
    CROSS = "CROSS"
    BLINK = "BLINK"
    UNKNOWN = "UNKNOWN"


_DEFAULTS = {
    "stable_frames": 3,  # 같은 관찰이 연속 N프레임이어야 상태를 바꾼다
    "no_signal_sec": 2.0,  # 신호등이 이 시간 넘게 안 보이면 NO_SIGNAL
    "frame_gap_sec": 1.0,  # 앞 프레임과 시각 차이가 이보다 크면 UNKNOWN
    "blink_window_sec": 2.0,  # 이 시간 안에 초록↔꺼짐이 2번 이상 바뀌면 BLINK
    "arm_sec": 2.0,  # 초록이 보이기 시작한 시각이 마지막 '빨간불 WAIT' 뒤 이 시간 안이어야 CROSS
    "cross_hold_sec": 1.0,  # CROSS 중 초록이 이 시간 넘게 안 보이면 UNKNOWN
}


def _observe(scene: SceneState) -> str | None:
    """이 프레임에서 믿을 수 있는 관찰 하나 (red / green / off), 없으면 None."""
    s = scene.signal
    if not s.present:
        return None
    if s.color in ("red", "green") and s.pos_check:
        return s.color
    if s.color == "off":
        return "off"
    return None  # unknown, 또는 위치가 어긋난 red/green


class SignalFSM:
    def __init__(self, config: dict) -> None:
        self.p = dict(_DEFAULTS)
        self.p.update((config or {}).get("fsm", {}) or {})
        self.state = State.UNKNOWN
        self._reset()
        self._prev_ts: float | None = None
        self._last_signal_ts: float | None = None  # 신호등이 마지막으로 보인 시각

    def _reset(self) -> None:
        """지금까지 본 것을 믿지 않고 처음부터 다시 본다 (끊김·신호등 사라짐·점멸 뒤)."""
        self._streak_obs: str | None = None
        self._streak = 0
        self._streak_start: float = 0.0
        self._last_wait_red_ts: float | None = None  # WAIT 상태에서 빨강을 마지막으로 본 시각
        self._last_green_ts: float | None = None
        self._flips: deque[tuple[float, str]] = deque()  # 점멸 판단용 (시각, green/off)

    def update(self, scene: SceneState) -> State:
        ts = scene.ts
        gap = self._prev_ts is not None and ts - self._prev_ts > self.p["frame_gap_sec"]
        self._prev_ts = ts

        # 1) 볼 수 없는 프레임, 또는 프레임이 끊김 → UNKNOWN, 처음부터 다시
        if not scene.frame_ok or gap:
            self._reset()
            self.state = State.UNKNOWN
            if not scene.frame_ok:
                return self.state

        # 2) 신호등이 안 보임 → 잠깐이면 그대로, 오래되면 NO_SIGNAL
        if not scene.signal.present:
            self._streak_obs, self._streak = None, 0
            if self._last_signal_ts is None or ts - self._last_signal_ts > self.p["no_signal_sec"]:
                self._reset()
                self.state = State.NO_SIGNAL
            return self._hold_check(ts)
        self._last_signal_ts = ts

        # 3) 관찰 연속 횟수 세기 (unknown 은 연속을 끊는다)
        obs = _observe(scene)
        if obs is None:
            self._streak_obs, self._streak = None, 0
            return self._hold_check(ts)
        if obs == self._streak_obs:
            self._streak += 1
        else:
            self._streak_obs, self._streak, self._streak_start = obs, 1, ts
        if obs == "green":
            self._last_green_ts = ts

        # 4) 점멸: 최근 blink_window_sec 안에 초록↔꺼짐이 2번 이상 바뀜
        #    빨강이 보이면 점멸 기록은 지운다 (점멸 다음은 빨간불 → WAIT 로 바로 넘어가야 한다)
        if obs == "red":
            self._flips.clear()
        elif not self._flips or self._flips[-1][1] != obs:
            self._flips.append((ts, obs))
        while self._flips and ts - self._flips[0][0] > self.p["blink_window_sec"]:
            self._flips.popleft()
        if obs != "red" and len(self._flips) >= 3:  # green→off→green (또는 off→green→off) = 2번 바뀜
            self.state = State.BLINK
            self._last_wait_red_ts = None  # 점멸 뒤에는 다시 빨간불부터 봐야 CROSS
            return self.state

        # 5) 같은 관찰이 stable_frames 연속일 때만 상태 변경
        if self._streak >= self.p["stable_frames"]:
            if obs == "red":
                self.state = State.WAIT
            elif obs == "green" and self.state != State.CROSS:
                armed = (
                    self._last_wait_red_ts is not None
                    and self._streak_start - self._last_wait_red_ts <= self.p["arm_sec"]
                )
                self.state = State.CROSS if armed else State.UNKNOWN
            elif obs == "off" and self.state != State.BLINK:
                self.state = State.UNKNOWN  # 계속 꺼져 있음 (고장·야간 점멸 등)
        if obs == "red" and self.state == State.WAIT:
            self._last_wait_red_ts = ts
        return self._hold_check(ts)

    def _hold_check(self, ts: float) -> State:
        """CROSS 는 초록이 계속 보일 때만 유지한다."""
        if self.state == State.CROSS and (
            self._last_green_ts is None or ts - self._last_green_ts > self.p["cross_hold_sec"]
        ):
            self.state = State.UNKNOWN
            self._last_wait_red_ts = None
        return self.state
