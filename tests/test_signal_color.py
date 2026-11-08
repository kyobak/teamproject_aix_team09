"""#6 신호색 판별 단위 테스트 — 합성 3칸 보행 신호등 (세로 30x96: 위=빨강 사람, 가운데=초록 사람, 아래=남은 시간 숫자).

완료 조건 8케이스: 낮 빨강/초록, 위치 어긋남 2개, 꺼짐, 역광, 야간 빨강/초록.
그 아래는 안전 규칙 보강 (숫자만 켜진 점멸 순간, 동시 점등, 쓸 수 없는 박스 등).
"""

import cv2
import numpy as np
import pytest

from walkaid.io.config import load_config
from walkaid.logic.signal_color import classify, classify_signal, measure

W, S = 30, 32  # 몸체 폭, 칸 높이
TOP, MID, BOT = (W // 2, S // 2), (W // 2, S + S // 2), (W // 2, 2 * S + S // 2)  # 칸 가운데

HOUSING = (25, 25, 25)
RED = (60, 30, 235)  # BGR, 빨간 LED
GREEN = (170, 225, 20)  # BGR, 보행 신호 청록
WHITE = (250, 250, 255)


@pytest.fixture(scope="module")
def config():
    return load_config()


def box(background=HOUSING) -> np.ndarray:
    return np.full((3 * S, W, 3), background, dtype=np.uint8)


def figure(img, center, color, r=9) -> np.ndarray:
    """사람 모양 대신 세로로 긴 타원 (LED 덩어리)."""
    cv2.ellipse(img, center, (r - 3, r), 0, 0, 360, color, -1)
    return img


def digits(img, color=GREEN) -> np.ndarray:
    """아래 칸에 두 자리 숫자 (세로 막대 두 개)."""
    x, y = BOT[0], BOT[1]
    cv2.rectangle(img, (x - 9, y - 8), (x - 3, y + 8), color, -1)
    cv2.rectangle(img, (x + 3, y - 8), (x + 9, y + 8), color, -1)
    return img


def night(center, color) -> np.ndarray:
    """야간: 주변은 거의 검정, 불 가운데는 하얗게 날아가고 둘레에 색 번짐."""
    img = box(background=(5, 5, 5))
    figure(img, center, color, r=11)
    figure(img, center, WHITE, r=5)
    return cv2.GaussianBlur(img, (5, 5), 0)


# ---- 완료 조건 8케이스 ----------------------------------------------------


def test_1_day_red_top(config):
    color, conf, pos = classify(figure(box(), TOP, RED), config)
    assert (color, pos) == ("red", True) and conf >= config["signal"]["min_conf"]


def test_2_day_green_mid(config):
    color, conf, pos = classify(figure(box(), MID, GREEN), config)
    assert (color, pos) == ("green", True) and conf >= config["signal"]["min_conf"]


def test_3_red_in_green_cell_is_unknown(config):
    assert classify(figure(box(), MID, RED), config) == ("unknown", 0.0, False)


def test_4_green_in_red_cell_is_unknown(config):
    assert classify(figure(box(), TOP, GREEN), config) == ("unknown", 0.0, False)


def test_5_all_off(config):
    color, _, pos = classify(box(), config)
    assert (color, pos) == ("off", False)


def test_6_backlight_washout_is_unknown(config):
    """역광: 몸체가 하얗게 날아가 색이 안 보임 → off 가 아니라 unknown (off 는 점멸로 해석될 수 있다)."""
    assert classify(box(background=(240, 242, 245)), config)[0] == "unknown"


def test_7_night_red(config):
    color, _, pos = classify(night(TOP, RED), config)
    assert (color, pos) == ("red", True)


def test_8_night_green(config):
    color, _, pos = classify(night(MID, GREEN), config)
    assert (color, pos) == ("green", True)


# ---- 안전 규칙 보강 ---------------------------------------------------------


def test_countdown_only_is_off_not_green(config):
    """초록 사람이 꺼지고 숫자만 켜진 순간(점멸) → off. green 으로 읽으면 점멸을 놓친다."""
    assert classify(digits(box()), config)[0] == "off"


def test_countdown_glow_spilling_into_mid_is_off(config):
    """숫자 빛이 가운데 칸으로 번져도 초록 사람이 아니다."""
    img = cv2.GaussianBlur(digits(box()), (15, 15), 0)
    img = cv2.GaussianBlur(digits(img), (9, 9), 0)
    m = measure(img, config)
    assert m.green_bottom > m.green_mid
    assert classify(img, config)[0] != "green"


def test_green_figure_with_countdown_is_green(config):
    assert classify(digits(figure(box(), MID, GREEN)), config)[0] == "green"


def test_red_and_green_together_is_unknown(config):
    assert classify(figure(figure(box(), TOP, RED), MID, GREEN), config)[0] == "unknown"


def test_min_conf_comes_from_config(config):
    strict = {"signal": {**config["signal"], "min_conf": 1.01}}
    assert classify(figure(box(), TOP, RED), strict)[0] == "unknown"


@pytest.mark.parametrize(
    "img",
    [None, np.zeros((0, 0, 3), np.uint8), np.zeros((5, 5, 3), np.uint8), np.zeros((96, 30), np.uint8)],
    ids=["none", "empty", "too-small", "grayscale"],
)
def test_unusable_box_is_unknown(img, config):
    assert classify(img, config) == ("unknown", 0.0, False)


def test_works_without_config():
    assert classify(figure(box(), TOP, RED), {})[0] == "red"


def test_pos_check_only_for_red_or_green(config):
    """scene-state 규칙 4: off·unknown 이면 pos_check 는 항상 False."""
    for img in (box(), figure(box(), MID, RED), figure(box(), TOP, GREEN), digits(box())):
        color, _, pos = classify(img, config)
        assert pos == (color in ("red", "green"))


def test_classify_signal_wraps_result(config):
    s = classify_signal(figure(box(), TOP, RED), config)
    assert s.present and s.color == "red" and s.pos_check
