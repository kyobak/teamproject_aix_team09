"""뼈대 테스트 — 파이프라인이 끝까지 돌고, 구현 전에는 CROSS 를 내지 않는다."""

from pathlib import Path

from tools.make_sample_video import make
from walkaid.logic.scene_state import SceneState, SignalInfo
from walkaid.logic.signal_fsm import SignalFSM, State
from walkaid.main import run
from walkaid.present.announcer import Announcer


def test_pipeline_runs_end_to_end(tmp_path: Path):
    said = run(str(make(tmp_path / "s.mp4")))
    assert said == ["신호등이 보이지 않습니다"]


def test_fsm_never_crosses_before_implementation():
    fsm = SignalFSM({})
    green = SceneState(ts=0.0, signal=SignalInfo(present=True, color="green", conf=0.99, pos_check=True))
    assert fsm.update(green) != State.CROSS


def test_frame_gap_goes_unknown():
    assert SignalFSM({}).update(SceneState(ts=0.0, frame_ok=False)) == State.UNKNOWN


def test_announcer_does_not_repeat():
    a = Announcer()
    assert a.announce(State.WAIT) is not None
    assert a.announce(State.WAIT) is None
