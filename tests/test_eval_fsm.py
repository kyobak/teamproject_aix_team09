"""상태 머신 안전 지표(tools/eval_fsm.py)를 합성 영상과 가짜 검출기로 검증한다."""

from pathlib import Path

import cv2
import numpy as np

from tools.eval_fsm import evaluate_fsm_clip, main, merge, red_to_green_starts
from walkaid.io.config import load_config
from walkaid.logic.scene_state import SceneState, SignalInfo
from walkaid.logic.signal_fsm import SignalFSM

BOX = [100, 200, 30, 90]


class FakeDetector:
    """초마다 정해진 색을 낸다. red·green 은 위치 확인(pos_check)을 통과한 것으로 본다."""

    def __init__(self, colors):
        self.colors = colors  # 초 -> 색, 또는 (초, 0.1초 단위) -> 색 함수

    def detect(self, image, ts):
        color = self.colors(ts) if callable(self.colors) else self.colors.get(int(ts))
        if color is None:
            return SceneState(ts=ts)
        return SceneState(ts=ts, signal=SignalInfo(present=True, color=color, pos_check=color in ("red", "green")))


def make_video(path: Path, seconds: int) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 64))
    for _ in range(30 * seconds):
        writer.write(np.zeros((64, 64, 3), np.uint8))
    writer.release()
    return path


def clip(labels, blink=None):
    return {"file": "x.mp4", "blink_sec": blink, "labels": [{"sec": s, "state": st, "box": BOX} for s, st in labels]}


def run(tmp_path, labels, colors, blink=None):
    seconds = max(s for s, _ in labels) + 1
    path = make_video(tmp_path / "x.mp4", seconds)
    config = load_config()
    return evaluate_fsm_clip(path, clip(labels, blink), FakeDetector(colors), SignalFSM(config), step=3)


def test_red_to_green_segments():
    states = {0: "red", 1: "red", 2: "green", 3: "green", 4: "blink", 5: "red", 6: "green"}
    assert red_to_green_starts(states) == [(2, 3), (6, 6)]
    assert red_to_green_starts({0: "green", 1: "green"}) == []  # 도착 때 이미 초록 → 대상 아님


def test_correct_detector_gives_cross_with_short_delay_and_no_danger(tmp_path):
    labels = [(0, "red"), (1, "red"), (2, "green"), (3, "green")]
    r = run(tmp_path, labels, {0: "red", 1: "red", 2: "green", 3: "green"})
    assert r["danger_cross_frames"] == 0 and r["danger_cross_events"] == 0
    assert r["green_segments"] == 1 and r["missed_cross"] == 0
    assert 0 < r["cross_delays_sec"][0] <= 0.5  # 초록 3프레임(0.1초 간격) 뒤 CROSS


def test_green_seen_during_real_red_is_a_danger_event(tmp_path):
    # 1초째는 정답이 빨강인데 검출기가 초록으로 봄 → 상태 머신이 CROSS → 위험 CROSS
    labels = [(0, "red"), (1, "red"), (2, "red")]
    r = run(tmp_path, labels, {0: "red", 1: "green", 2: "red"})
    assert r["danger_cross_events"] == 1
    assert r["danger_cross_frames"] > 0


def test_arriving_on_green_is_unknown_not_cross(tmp_path):
    labels = [(0, "green"), (1, "green"), (2, "green")]
    r = run(tmp_path, labels, {0: "green", 1: "green", 2: "green"})
    assert r["green_segments"] == 0
    assert "green|CROSS" not in r["by_truth"]
    assert r["by_truth"]["green|UNKNOWN"] > 0


def test_missed_cross_when_detector_never_sees_green(tmp_path):
    labels = [(0, "red"), (1, "red"), (2, "green"), (3, "green")]
    r = run(tmp_path, labels, {0: "red", 1: "red"})  # 2초부터 신호등 미검출
    assert r["missed_cross"] == 1 and r["cross_delays_sec"] == []


def test_merge_totals_and_unknown_ratio():
    a = {
        "by_truth": {"red|WAIT": 8, "red|UNKNOWN": 2},
        "danger_cross_frames": 0,
        "danger_cross_events": 0,
        "green_segments": 1,
        "cross_delays_sec": [0.3],
        "missed_cross": 0,
    }
    b = {
        "by_truth": {"green|CROSS": 5, "green|UNKNOWN": 5},
        "danger_cross_frames": 1,
        "danger_cross_events": 1,
        "green_segments": 2,
        "cross_delays_sec": [0.5],
        "missed_cross": 1,
    }
    total = merge([a, b])
    assert total["frames"] == 20
    assert total["unknown_ratio"] == 0.35
    assert total["unknown_ratio_by_truth"] == {"red": 0.2, "green": 0.5}
    assert total["danger_cross_events"] == 1 and total["missed_cross"] == 1
    assert total["cross_delay_median_sec"] == 0.4 and total["cross_delay_max_sec"] == 0.5


def test_main_reports_missing_videos(tmp_path: Path, capsys):
    assert main(["--videos", str(tmp_path)]) == 1
    assert "평가한 영상이 없습니다" in capsys.readouterr().out
