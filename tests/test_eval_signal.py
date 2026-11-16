"""평가 스크립트의 채점 규칙을 합성 영상과 가짜 검출기로 검증한다."""

import json
from pathlib import Path

import cv2
import numpy as np

from tools.eval_signal import (
    DEFAULT_GT,
    evaluate_clip,
    judge,
    load_labels,
    longest_runs,
    main,
    near_box,
    truth_at,
)
from walkaid.logic.scene_state import SceneState, SignalInfo

BOX = [100, 200, 30, 90]


class FakeDetector:
    """ts 에 따라 정해진 색을 내는 검출기. last_box 로 위치도 알려 준다."""

    def __init__(self, colors, box=BOX):
        self.colors = colors  # 초 -> 색
        self.last_box = box

    def detect(self, image, ts):
        color = self.colors.get(int(ts))
        return SceneState(ts=ts, signal=SignalInfo(present=color is not None, color=color or "unknown"))


def make_video(path: Path, seconds: int) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 64))
    for _ in range(30 * seconds):
        writer.write(np.zeros((64, 64, 3), np.uint8))
    writer.release()
    return path


def clip(labels, blink=None):
    return {"file": "x.mp4", "blink_sec": blink, "labels": [{"sec": s, "state": st, "box": BOX} for s, st in labels]}


def test_blink_window_turns_labels_into_blink():
    states, _ = load_labels(clip([(0, "red"), (1, "green"), (2, "off"), (3, "green")], blink=[2, 3]))
    assert states == {0: "red", 1: "green", 2: "blink", 3: "blink"}


def test_frames_near_a_label_change_are_skipped():
    states = {0: "red", 1: "green"}
    assert truth_at(5, states) == "red"
    assert truth_at(25, states) is None  # 30번째 프레임에서 초록으로 바뀜 → 앞 10프레임 제외
    assert truth_at(35, states) is None
    assert truth_at(45, states) == "green"
    assert truth_at(65, states) is None  # 2초는 정답 없음


def test_location_rule():
    assert near_box([100, 200, 30, 90], BOX)
    assert near_box([110, 210, 30, 90], BOX)
    assert not near_box([300, 200, 30, 90], BOX)
    assert not near_box(None, BOX)


def test_judge_marks_other_locations_and_skips_check_without_last_box():
    scene = SceneState(ts=0, signal=SignalInfo(present=True, color="green"))
    assert judge(scene, FakeDetector({}, box=BOX), BOX) == "green"
    assert judge(scene, FakeDetector({}, box=[600, 200, 30, 90]), BOX) == "green*"
    assert judge(scene, object(), BOX) == "green"  # last_box 없는 검출기
    assert judge(SceneState(ts=0), FakeDetector({}), BOX) == "none"


def test_longest_run():
    assert longest_runs([True, True, False, True, True, True, False]) == 3
    assert longest_runs([]) == 0


def test_evaluate_clip_counts_and_red_green_run(tmp_path: Path):
    path = make_video(tmp_path / "x.mp4", seconds=3)
    labels = clip([(0, "red"), (1, "red"), (2, "green")])
    detector = FakeDetector({0: "red", 1: "green", 2: "green"})  # 1초째 빨간불을 green 으로 봄
    counts, run = evaluate_clip(path, labels, detector, step=3)
    assert counts[("red", "red")] == 10  # 0초: 0~27 프레임
    assert counts[("red", "green")] == 7  # 1초: 30~48 (51부터는 2초 경계 근처라 제외)
    assert counts[("green", "green")] == 6  # 2초: 72~87 (60~69는 경계 근처라 제외)
    assert run == 7


def test_ground_truth_file_is_consistent():
    gt = json.loads(DEFAULT_GT.read_text(encoding="utf-8"))
    assert len(gt["clips"]) == 12
    assert sum(len(c["labels"]) for c in gt["clips"]) == 558
    for c in gt["clips"]:
        assert c["split"] in {"dev", "test"} and c["lighting"] in {"day", "dusk", "night"}
        for row in c["labels"]:
            assert row["state"] in {"red", "green", "off"} and len(row["box"]) == 4


def test_main_reports_missing_videos(tmp_path: Path, capsys):
    assert main(["--videos", str(tmp_path)]) == 1
    assert "평가한 영상이 없습니다" in capsys.readouterr().out
