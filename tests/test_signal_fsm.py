"""상태 머신 테스트 (#7). 영상 없이 SceneState 를 직접 만들어 넣는다.

5fps(0.2초 간격)를 가정한다. 완료 조건:
- 빨간불·점멸 중 CROSS 안내 0회
- 도착 시 이미 초록이면 CROSS 를 내지 않는다
- 프레임이 끊기면 UNKNOWN
"""

from __future__ import annotations

import random

import pytest

from walkaid.io.config import load_config
from walkaid.logic.scene_state import SceneState, SignalInfo
from walkaid.logic.signal_fsm import SignalFSM, State

DT = 0.2  # 5fps


def obs(color: str | None, ts: float, pos_check: bool | None = None, frame_ok: bool = True) -> SceneState:
    """color=None 이면 신호등 없음. red/green 은 기본으로 위치 확인(pos_check)된 것으로 만든다."""
    if not frame_ok:
        return SceneState(ts=ts, frame_ok=False)
    if color is None:
        return SceneState(ts=ts)
    if pos_check is None:
        pos_check = color in ("red", "green")
    conf = 0.0 if color == "unknown" else 0.9
    return SceneState(ts=ts, signal=SignalInfo(present=True, color=color, conf=conf, pos_check=pos_check))


class Feeder:
    """색 순서를 0.2초 간격으로 넣고, 매 프레임 상태를 기록한다."""

    def __init__(self, config: dict | None = None) -> None:
        self.fsm = SignalFSM(load_config() if config is None else config)
        self.ts = 0.0
        self.states: list[State] = []

    def feed(self, *colors: str | None) -> State:
        for c in colors:
            self.states.append(self.fsm.update(obs(c, self.ts)))
            self.ts += DT
        return self.fsm.state

    def raw(self, scene: SceneState) -> State:
        self.states.append(self.fsm.update(scene))
        self.ts = scene.ts + DT
        return self.fsm.state


@pytest.fixture
def f() -> Feeder:
    return Feeder()


# ---- 1. 기본 전환 ---------------------------------------------------------------------------


def test_1_three_reds_is_wait(f):
    assert f.feed("red", "red") != State.WAIT
    assert f.feed("red") == State.WAIT


def test_2_wait_then_three_greens_is_cross(f):
    f.feed("red", "red", "red")
    assert f.feed("green", "green") == State.WAIT  # 아직 2프레임
    assert f.feed("green") == State.CROSS


def test_3_short_green_is_ignored(f):
    f.feed("red", "red", "red")
    assert f.feed("green", "green", "red") == State.WAIT
    assert f.feed("green", "red", "green") == State.WAIT
    assert State.CROSS not in f.states


def test_cross_then_three_reds_is_wait(f):
    f.feed("red", "red", "red", "green", "green", "green")
    assert f.feed("red", "red", "red") == State.WAIT


# ---- 2. 도착 시 이미 초록 --------------------------------------------------------------------


def test_4_arrive_on_green_is_not_cross(f):
    f.feed(*["green"] * 20)
    assert State.CROSS not in f.states
    assert f.fsm.state == State.UNKNOWN


def test_arm_expires_if_red_seen_long_ago(f):
    # 빨간불을 보고 → 3초 동안 판단 불가 → 초록: 그사이 초록이 이미 한참 지났을 수 있으니 CROSS 아님
    f.feed("red", "red", "red")
    f.feed(*["unknown"] * 15)
    f.feed("green", "green", "green", "green")
    assert State.CROSS not in f.states


def test_short_unknown_between_red_and_green_still_crosses(f):
    # 바뀌는 순간 0.4초 판단 불가는 흔하다 (eval.md: 바뀌는 순간 앞뒤 0.3초)
    f.feed("red", "red", "red", "unknown", "unknown")
    assert f.feed("green", "green", "green") == State.CROSS


# ---- 3. 점멸 -------------------------------------------------------------------------------


def test_5_green_off_alternating_is_blink_and_never_cross(f):
    f.feed("red", "red", "red", "green", "green", "green")  # CROSS
    f.feed("off", "green", "green", "green", "off")
    assert f.fsm.state == State.BLINK
    f.feed(*["green", "green", "green", "green", "off"] * 4)  # 점멸이 이어짐
    blink_start = f.states.index(State.BLINK)
    assert State.CROSS not in f.states[blink_start:]


def test_arrive_during_blink_is_blink_not_cross(f):
    f.feed(*["green", "green", "green", "off"] * 5)
    assert f.fsm.state == State.BLINK
    assert State.CROSS not in f.states


def test_after_blink_needs_red_again_before_cross(f):
    f.feed("red", "red", "red", "green", "green", "green")
    f.feed(*["off", "green", "green", "green"] * 3)  # 점멸
    f.feed("red", "red", "red")
    assert f.fsm.state == State.WAIT
    assert f.feed("green", "green", "green") == State.CROSS  # 다음 주기는 정상


def test_steady_off_is_unknown(f):
    f.feed("red", "red", "red")
    assert f.feed("off", "off", "off") == State.UNKNOWN


# ---- 4. 프레임 문제 -------------------------------------------------------------------------


def test_6_bad_frame_is_unknown_and_resets(f):
    f.feed("red", "red", "red")
    assert f.raw(obs(None, f.ts, frame_ok=False)) == State.UNKNOWN
    # 끊긴 뒤에는 처음부터 — 초록만 보이면 CROSS 아님
    assert f.feed("green", "green", "green") == State.UNKNOWN


def test_6_time_gap_over_one_second_is_unknown(f):
    f.feed("red", "red", "red", "green", "green", "green")  # CROSS
    assert f.raw(obs("green", f.ts + 1.5)) == State.UNKNOWN
    assert f.feed("green", "green", "green") == State.UNKNOWN


def test_brief_signal_loss_keeps_state(f):
    f.feed("red", "red", "red")
    assert f.feed(None, None, None) == State.WAIT  # 0.6초는 그대로
    assert f.feed("red") == State.WAIT


def test_long_signal_loss_is_no_signal(f):
    f.feed("red", "red", "red")
    assert f.feed(*[None] * 12) == State.NO_SIGNAL  # 2.4초


def test_never_seen_signal_is_no_signal(f):
    assert f.feed(None) == State.NO_SIGNAL


# ---- 5. unknown 은 CROSS 를 만들지도, 붙잡지도 않는다 ---------------------------------------------


def test_7_unknown_breaks_green_streak(f):
    f.feed("red", "red", "red")
    f.feed("green", "unknown", "green", "unknown", "green", "green")
    assert State.CROSS not in f.states


def test_position_mismatch_is_not_counted(f):
    f.feed("red", "red", "red")
    for _ in range(5):
        f.raw(obs("green", f.ts, pos_check=False))
    assert State.CROSS not in f.states


def test_cross_does_not_survive_long_unknown(f):
    # 초록 → (실제로는 빨강인데) unknown 만 나옴 → CROSS 가 남아 있으면 위험
    f.feed("red", "red", "red", "green", "green", "green")
    f.feed(*["unknown"] * 6)  # 1.2초
    assert f.fsm.state == State.UNKNOWN


def test_cross_does_not_survive_signal_loss(f):
    f.feed("red", "red", "red", "green", "green", "green")
    f.feed(*[None] * 6)
    assert f.fsm.state != State.CROSS


# ---- 6. 안전 성질: 어떤 순서가 들어와도 -----------------------------------------------------------


@pytest.mark.parametrize("seed", range(200))
def test_cross_only_after_three_greens_preceded_by_wait(seed):
    """무작위 관찰 순서에서 CROSS 가 나온 프레임은 반드시
    (1) 직전 3프레임이 모두 위치 확인된 초록이고 (2) 그 전에 WAIT 상태가 있었다."""
    rng = random.Random(seed)
    f = Feeder()
    colors = rng.choices(["red", "green", "off", "unknown", None], weights=[4, 4, 2, 2, 1], k=150)
    f.feed(*colors)
    for i, st in enumerate(f.states):
        if st == State.CROSS and (i == 0 or f.states[i - 1] != State.CROSS):  # CROSS 로 바뀐 프레임
            assert colors[i - 2 : i + 1] == ["green"] * 3
            assert State.WAIT in f.states[:i]


def test_works_without_config():
    f = Feeder(config={})
    f.feed("red", "red", "red")
    assert f.feed("green", "green", "green") == State.CROSS
