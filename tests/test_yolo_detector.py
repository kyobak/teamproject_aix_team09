"""D1 연결과 실패 경로는 합성 프레임·모의 YOLO로 검증한다. 가중치·네트워크 불필요."""

import builtins
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from tools.make_sample_video import make
from walkaid.io.config import load_config
from walkaid.logic.detector import make_detector, yolo
from walkaid.logic.signal_fsm import SignalFSM, State
from walkaid.main import run


class Tensor:
    def __init__(self, values):
        self.values = np.asarray(values, dtype=np.float32)

    def cpu(self):
        return self

    def numpy(self):
        return self.values


class Model:
    names = {2: "traffic light", 9: "boat"}

    def __init__(self, rows=()):
        self.rows = rows
        self.calls = []

    def predict(self, **kwargs):
        self.calls.append(kwargs)
        data = np.asarray(self.rows, dtype=np.float32).reshape(-1, 6)
        boxes = SimpleNamespace(xyxy=Tensor(data[:, :4]), conf=Tensor(data[:, 4]), cls=Tensor(data[:, 5]))
        return [SimpleNamespace(boxes=boxes)]


def image(color=None, x=50, y=30, w=30, h=96):
    frame = np.full((360, 240, 3), 180, dtype=np.uint8)
    draw(frame, color, x, y, w, h)
    return frame


def draw(frame, color, x, y, w=30, h=96):
    frame[y : y + h, x : x + w] = 25
    if color is not None:
        center = (x + w // 2, y + h // 6 * (1 if color == "red" else 3))
        cv2.ellipse(frame, center, (6, 9), 0, 0, 360, (60, 30, 235) if color == "red" else (170, 225, 20), -1)


@pytest.mark.parametrize(("color", "expected"), [("red", "red"), ("green", "green"), (None, "off")])
def test_yolo_crop_uses_existing_color_classifier(color, expected):
    model = Model([(50, 30, 80, 126, 0.9, 2)])
    detector = yolo.YOLODetector(load_config(), model=model)
    scene = detector.detect(image(color), 12.5)
    assert scene.ts == 12.5
    assert scene.signal.present and scene.signal.color == expected
    assert scene.signal.pos_check == (expected in ("red", "green"))
    assert detector.last_box == (50, 30, 30, 96)
    call = model.calls[0]
    assert call["source"].shape == (234, 240, 3)
    assert call["classes"] == [2]  # COCO ID를 9로 고정하지 않는다.
    assert call["conf"] == 0.25 and call["imgsz"] == 640 and call["device"] == "cpu"
    assert call["save"] is False


@pytest.mark.parametrize(
    "row",
    [
        (50, 30, 80, 126, 0.1, 2),  # 낮은 YOLO 확신
        (50, 30, 80, 126, 0.9, 9),  # 다른 클래스
        (10, 10, 170, 40, 0.9, 2),  # 가로 차량 신호등
        (50, 30, 55, 46, 0.9, 2),  # 너무 작음
        (500, 30, 530, 126, 0.9, 2),  # 화면 밖
        (80, 126, 50, 30, 0.9, 2),  # 뒤집힌 박스
        (float("nan"), 30, 80, 126, 0.9, 2),
    ],
)
def test_rejected_proposals_do_not_become_a_signal(row):
    scene = yolo.YOLODetector(load_config(), model=Model([row])).detect(image("red"), 0)
    assert not scene.signal.present
    assert scene.signal.color == "unknown" and not scene.signal.pos_check


def test_conflicting_similar_signals_remain_unknown():
    frame = image("red", x=20)
    draw(frame, "green", 150, 30)
    model = Model([(20, 30, 50, 126, 0.9, 2), (150, 30, 180, 126, 0.9, 2)])
    detector = yolo.YOLODetector(load_config(), model=model)
    scene = detector.detect(frame, 0)
    assert scene.signal.present and scene.signal.color == "unknown"
    assert detector.last_box is None


def test_largest_body_is_selected_when_smaller_candidate_is_not_comparable():
    frame = image("green", x=120, y=30, w=45, h=144)
    draw(frame, "red", 20, 30)
    model = Model([(20, 30, 50, 126, 0.9, 2), (120, 30, 165, 174, 0.9, 2)])
    detector = yolo.YOLODetector(load_config(), model=model)
    scene = detector.detect(frame, 0)
    assert detector.last_box == (120, 30, 45, 144)
    assert scene.signal.color == "green"


def test_switching_to_a_distant_green_does_not_arm_cross():
    config = load_config()
    model = Model()
    detector = yolo.YOLODetector(config, model=model)
    fsm = SignalFSM(config)
    states = []
    for index in range(18):
        red = index < 3
        x = 20 if red else 150
        model.rows = [(x, 30, x + 30, 126, 0.9, 2)]
        scene = detector.detect(image("red" if red else "green", x=x), index * 0.2)
        states.append(fsm.update(scene))
    assert State.WAIT in states
    assert State.CROSS not in states
    assert scene.signal.color == "green"


@pytest.mark.parametrize(
    "frame",
    [
        None,
        np.zeros((10, 10, 3), dtype=np.uint8),
        np.zeros((0, 0, 3), dtype=np.uint8),
        np.ones((10, 10), dtype=np.uint8),
        np.ones((10, 10, 4), dtype=np.uint8),
    ],
)
def test_unusable_frame_is_not_sent_to_model(frame):
    model = Model()
    scene = yolo.YOLODetector(load_config(), model=model).detect(frame, 0)
    assert not scene.frame_ok and not scene.signal.present
    assert model.calls == []


def test_no_detection_clears_the_last_display_box():
    model = Model([(50, 30, 80, 126, 0.9, 2)])
    detector = yolo.YOLODetector(load_config(), model=model)
    detector.detect(image("red"), 0)
    assert detector.last_box is not None
    model.rows = []
    assert not detector.detect(image("red"), 0.2).signal.present
    assert detector.last_box is None


def test_factory_and_main_pipeline_accept_d1(tmp_path: Path, monkeypatch):
    model = Model()
    monkeypatch.setattr(yolo, "_load_model", lambda path: model)
    assert isinstance(make_detector("d1", load_config()), yolo.YOLODetector)
    assert run(str(make(tmp_path / "sample.mp4")), detector_name="d1") == ["신호등이 보이지 않습니다"]
    assert model.calls


def test_d0_can_start_without_ultralytics():
    code = (
        "import sys; sys.modules['ultralytics']=None; "
        "from walkaid.logic.detector import make_detector; "
        "assert make_detector('d0', {}) is not None"
    )
    subprocess.run([sys.executable, "-c", code], check=True, cwd=Path(__file__).resolve().parents[1])


def test_missing_model_fails_before_attempting_download(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="D1 모델"):
        yolo._load_model(tmp_path / "missing.pt")


def test_missing_optional_package_explains_installation(tmp_path: Path, monkeypatch):
    weights = tmp_path / "weights.pt"
    weights.write_bytes(b"not-used")
    original = builtins.__import__

    def without_ultralytics(name, *args, **kwargs):
        if name == "ultralytics":
            raise ImportError("not installed")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_ultralytics)
    with pytest.raises(RuntimeError, match="requirements-yolo"):
        yolo._load_model(weights)


def test_wrong_model_classes_are_rejected():
    model = Model()
    model.names = {0: "ped_red", 1: "ped_green"}
    with pytest.raises(ValueError, match="COCO"):
        yolo.YOLODetector(load_config(), model=model)
