"""#6 신호색 판별 단위 테스트 — 합성 신호등 박스(세로 40x100, 위=빨강 칸, 아래=초록 칸).

완료 조건 8케이스: 낮 빨강/초록, 위치 어긋남 2개, 꺼짐, 역광, 야간 빨강/초록.
그 아래는 안전 규칙(scene-state.md 지켜야 할 규칙 2~4) 보강 테스트.
"""

import cv2
import numpy as np
import pytest

from walkaid.io.config import load_config
from walkaid.logic.signal_color import classify, classify_signal, measure

W, H = 40, 100
TOP, BOTTOM = (W // 2, H // 4), (W // 2, 3 * H // 4)  # 위·아래 칸 중심

HOUSING = (30, 30, 30)  # 검은 몸체
RED = (40, 40, 230)  # BGR, H≈0
GREEN = (160, 220, 0)  # BGR, 보행 신호 청록색, H≈82
WHITE_CORE = (250, 250, 255)


@pytest.fixture(scope="module")
def config():
    return load_config()


def box(background=HOUSING) -> np.ndarray:
    return np.full((H, W, 3), background, dtype=np.uint8)


def lamp(img: np.ndarray, center, color, radius=12) -> np.ndarray:
    cv2.circle(img, center, radius, color, -1)
    return img


def night_lamp(center, color) -> np.ndarray:
    """야간: 주변은 거의 검정, 불 가운데는 하얗게 날아가고 둘레에 색 번짐."""
    img = box(background=(5, 5, 5))
    cv2.circle(img, center, 15, color, -1)
    cv2.circle(img, center, 6, WHITE_CORE, -1)
    return cv2.GaussianBlur(img, (5, 5), 0)


# ---- 완료 조건 8케이스 ----------------------------------------------------


def test_1_day_red_top(config):
    s = classify_signal(lamp(box(), TOP, RED), config)
    assert (s.color, s.pos_check) == ("red", True)
    assert s.conf >= config["signal"]["min_conf"]


def test_2_day_green_bottom(config):
    s = classify_signal(lamp(box(), BOTTOM, GREEN), config)
    assert (s.color, s.pos_check) == ("green", True)
    assert s.conf >= config["signal"]["min_conf"]


def test_3_red_at_bottom_is_unknown(config):
    s = classify_signal(lamp(box(), BOTTOM, RED), config)
    assert (s.color, s.pos_check, s.conf) == ("unknown", False, 0.0)


def test_4_green_at_top_is_unknown(config):
    s = classify_signal(lamp(box(), TOP, GREEN), config)
    assert (s.color, s.pos_check, s.conf) == ("unknown", False, 0.0)


def test_5_both_lamps_off(config):
    img = lamp(lamp(box(), TOP, (45, 45, 50)), BOTTOM, (45, 50, 45))  # 꺼진 칸은 어두운 회색
    s = classify_signal(img, config)
    assert (s.color, s.pos_check) == ("off", False)


def test_6_backlight_washout_is_unknown(config):
    """역광: 몸체 전체가 하얗게 날아가 색이 안 보임 → off 가 아니라 unknown."""
    img = lamp(box(background=(235, 238, 240)), BOTTOM, (240, 250, 245))
    s = classify_signal(img, config)
    assert (s.color, s.pos_check) == ("unknown", False)


def test_7_night_red(config):
    s = classify_signal(night_lamp(TOP, RED), config)
    assert (s.color, s.pos_check) == ("red", True)


def test_8_night_green(config):
    s = classify_signal(night_lamp(BOTTOM, GREEN), config)
    assert (s.color, s.pos_check) == ("green", True)


# ---- 안전 규칙 보강 ---------------------------------------------------------


def test_both_colors_lit_is_unknown(config):
    """위 빨강 + 아래 초록이 동시에 보이면 어느 쪽도 믿지 않는다."""
    s = classify_signal(lamp(lamp(box(), TOP, RED), BOTTOM, GREEN), config)
    assert s.color == "unknown"


def test_red_hue_wraparound_170_179(config):
    """빨강은 H 0~10 과 170~179 두 구간 — 170 쪽 빨강도 잡아야 한다."""
    magenta_red = (90, 20, 230)
    h = cv2.cvtColor(np.uint8([[magenta_red]]), cv2.COLOR_BGR2HSV)[0, 0, 0]
    assert h >= 170
    assert classify_signal(lamp(box(), TOP, magenta_red), config).color == "red"


def test_low_confidence_becomes_unknown(config):
    """불이 아주 작게만 보이면(밝기 부족) conf 가 min_conf 를 못 넘어 unknown."""
    s = classify_signal(lamp(box(), BOTTOM, GREEN, radius=4), config)
    assert s.color == "unknown" and s.pos_check is False


def test_min_conf_comes_from_config(config):
    strict = {"signal": {**config["signal"], "min_conf": 1.01}}
    assert classify_signal(lamp(box(), TOP, RED), strict).color == "unknown"


@pytest.mark.parametrize(
    "img",
    [None, np.zeros((0, 0, 3), np.uint8), np.zeros((5, 5, 3), np.uint8), np.zeros((H, W), np.uint8)],
    ids=["none", "empty", "too-small", "grayscale"],
)
def test_unusable_box_is_unknown(img, config):
    s = classify_signal(img, config)
    assert (s.present, s.color, s.conf, s.pos_check) == (True, "unknown", 0.0, False)


def test_works_without_config():
    assert classify_signal(lamp(box(), TOP, RED), {}).color == "red"


def test_pos_check_only_for_red_or_green(config):
    """scene-state 규칙 4: off·unknown 이면 pos_check 는 항상 False."""
    imgs = [box(), lamp(box(), BOTTOM, RED), lamp(box(), TOP, GREEN), box(background=(240, 240, 240))]
    for img in imgs:
        s = classify_signal(img, config)
        assert s.pos_check == (s.color in ("red", "green"))


def test_measure_splits_top_and_bottom(config):
    m = measure(lamp(box(), TOP, RED), config)
    assert m.red_top > 0.1 and m.red_bottom == 0.0 and m.green_top == 0.0


def test_classify_returns_tuple_for_fsm_integration(config):
    """#7·#5 연결용 형식: classify(crop, config) -> (color, conf, pos_check)."""
    color, conf, pos_check = classify(lamp(box(), TOP, RED), config)
    assert (color, pos_check) == ("red", True) and conf >= config["signal"]["min_conf"]
    assert classify(None, config) == ("unknown", 0.0, False)
