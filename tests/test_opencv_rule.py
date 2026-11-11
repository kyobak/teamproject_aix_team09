"""#5 D0 검출기 테스트 — 합성 거리 화면(1080x1920, 세로 영상)에 3칸 보행 신호등을 그려 넣고 찾는지 본다."""

import cv2
import numpy as np
import pytest

from walkaid.io.config import load_config
from walkaid.logic.detector import make_detector
from walkaid.logic.detector.opencv_rule import OpenCVRuleDetector

RED = (60, 30, 235)
GREEN = (170, 225, 20)
HOUSING = (25, 25, 25)


@pytest.fixture(scope="module")
def config():
    return load_config()


def street() -> np.ndarray:
    """밝은 하늘(위) + 회색 건물(가운데) + 도로(아래)."""
    img = np.full((1920, 1080, 3), (215, 195, 170), np.uint8)
    img[900:1300] = (150, 150, 150)
    img[1300:] = (90, 90, 90)
    return img


def signal(img, x, y, state: str, cell=30) -> np.ndarray:
    """(x, y) 에 세로 3칸 몸체. state: red / green / countdown(숫자만) / off."""
    w = cell
    cv2.rectangle(img, (x, y), (x + w, y + 3 * cell), HOUSING, -1)
    cx = x + w // 2
    if state == "red":
        cv2.ellipse(img, (cx, y + cell // 2), (cell // 4, cell // 3), 0, 0, 360, RED, -1)
    if state == "green":
        cv2.ellipse(img, (cx, y + cell + cell // 2), (cell // 4, cell // 3), 0, 0, 360, GREEN, -1)
    if state == "countdown":
        yb = y + 2 * cell + cell // 2
        cv2.rectangle(img, (cx - 9, yb - 8), (cx - 3, yb + 8), GREEN, -1)
        cv2.rectangle(img, (cx + 3, yb - 8), (cx + 9, yb + 8), GREEN, -1)
    return img


def near(box, x, y, tol=15):
    return abs(box[0] - x) < tol and abs(box[1] - y) < tol


def test_finds_red_signal(config):
    det = OpenCVRuleDetector(config)
    s = det.detect(signal(street(), 500, 600, "red"), ts=0.0)
    assert s.signal.present and s.signal.color == "red" and s.signal.pos_check
    assert near(det.last_box, 500, 600)


def test_finds_green_signal(config):
    det = OpenCVRuleDetector(config)
    s = det.detect(signal(street(), 500, 600, "green"), ts=0.0)
    assert s.signal.color == "green" and s.signal.pos_check
    assert near(det.last_box, 500, 600)


def test_countdown_only_is_off_not_green(config):
    """숫자만 켜진 점멸 순간: 숫자를 초록 사람으로 읽지 않고, 몸체 위치도 맞게 잡는다 (낮 — 몸체 위가 밝은 하늘)."""
    det = OpenCVRuleDetector(config)
    s = det.detect(signal(street(), 500, 600, "countdown"), ts=0.0)
    assert s.signal.color != "green"
    if det.last_box is not None:  # 숫자 조각만 보고 잡은 박스는 크기가 부정확할 수 있다 → 몸체와 겹치는지만 본다
        x, y, w, h = det.last_box
        assert 500 <= x + w / 2 <= 530 and 600 <= y + h / 2 <= 690


def test_no_signal_on_empty_street(config):
    s = OpenCVRuleDetector(config).detect(street(), ts=0.0)
    assert not s.signal.present


def test_red_blob_without_housing_is_rejected(config):
    """간판·후미등처럼 둘레에 검은 몸체가 없는 빨간 덩어리는 신호등이 아니다."""
    img = street()
    cv2.ellipse(img, (515, 615), (8, 10), 0, 0, 360, RED, -1)
    det = OpenCVRuleDetector(config)
    assert not det.detect(img, ts=0.0).signal.present


def test_conflicting_signals_give_unknown_not_green(config):
    """비슷한 신호등 두 개가 서로 다른 색(빨강·초록)이면 어느 것이 내 신호인지 모른다 → green 을 내지 않는다."""
    img = signal(signal(street(), 300, 600, "red"), 700, 600, "green")
    s = OpenCVRuleDetector(config).detect(img, ts=0.0)
    assert s.signal.present and s.signal.color == "unknown"


def test_once_tracked_other_signal_does_not_steal(config):
    """혼자 보일 때 찾은 신호등은, 나중에 다른 색 신호등이 화면에 들어와도 계속 그것을 본다."""
    det = OpenCVRuleDetector(config)
    det.detect(signal(street(), 300, 600, "red"), ts=0.0)
    s = det.detect(signal(signal(street(), 300, 600, "red"), 700, 600, "green"), ts=0.2)
    assert s.signal.color == "red" and near(det.last_box, 300, 600)


def test_tracking_keeps_signal_when_all_lamps_off(config):
    """빨강으로 한 번 찾은 몸체는 불이 다 꺼진 순간에도 같은 위치에서 off 로 본다 (점멸 판단용)."""
    det = OpenCVRuleDetector(config)
    det.detect(signal(street(), 500, 600, "red"), ts=0.0)
    s = det.detect(signal(street(), 503, 602, "off"), ts=0.2)
    assert s.signal.present and s.signal.color == "off"
    assert near(det.last_box, 503, 602, tol=8)


def test_tracking_does_not_slide_down_to_countdown(config):
    """초록 → 숫자만 켜짐으로 바뀌어도 박스가 숫자 칸 쪽으로 끌려 내려가지 않는다."""
    det = OpenCVRuleDetector(config)
    det.detect(signal(street(), 500, 600, "green"), ts=0.0)
    s = det.detect(signal(street(), 500, 600, "countdown"), ts=0.2)
    assert s.signal.color == "off"
    assert near(det.last_box, 500, 600, tol=15)


def test_lower_part_of_frame_is_ignored(config):
    s = OpenCVRuleDetector(config).detect(signal(street(), 500, 1500, "red"), ts=0.0)
    assert not s.signal.present


@pytest.mark.parametrize("img", [np.zeros((1920, 1080, 3), np.uint8), np.zeros((0, 0, 3), np.uint8)])
def test_unusable_frame(img, config):
    s = OpenCVRuleDetector(config).detect(img, ts=1.0)
    assert s.frame_ok is False and not s.signal.present


def test_make_detector_d0(config):
    assert isinstance(make_detector("d0", config), OpenCVRuleDetector)
