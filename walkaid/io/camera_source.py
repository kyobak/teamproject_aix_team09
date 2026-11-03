"""웹캠과 mp4를 같은 방식으로 읽는다.

`frames()` 하나만 바깥에 보여 준다. 로직 계층은 입력이 웹캠인지 파일인지 모른다.
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterator
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class Frame:
    image: np.ndarray  # BGR
    ts: float  # 초 단위 시각 (파일이면 영상 안의 시각)


def frames(source: str, max_fps: float | None = None) -> Iterator[Frame]:
    """숫자는 웹캠 번호, 나머지는 파일 경로. BGR 이미지와 초 단위 시각을 낸다.

    파일의 시각은 영상 안의 시각, 웹캠의 시각은 Unix 시각이다.
    max_fps는 프레임을 건너뛰어 출력 빈도를 제한하며 재생을 지연하지 않는다.
    중간에 멈추는 호출자는 반환된 제너레이터의 close()를 호출해야 한다.
    """
    if max_fps is not None and (not math.isfinite(max_fps) or max_fps <= 0):
        raise ValueError("max_fps는 양의 유한한 수여야 합니다")
    cap = cv2.VideoCapture(int(source)) if source.isdigit() else cv2.VideoCapture(source)
    is_file = not source.isdigit()
    min_gap = 1.0 / max_fps if max_fps is not None else 0.0
    last_ts = -math.inf
    previous_ts = -math.inf
    index = 0
    try:
        if not cap.isOpened():
            raise FileNotFoundError(f"입력을 열 수 없습니다: {source}")
        fps = cap.get(cv2.CAP_PROP_FPS) if is_file else 0.0
        while True:
            ok, image = cap.read()
            if not ok:
                break
            ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0 if is_file else time.time()
            if is_file and (not math.isfinite(ts) or ts < 0 or ts <= previous_ts):
                if not math.isfinite(fps) or fps <= 0:
                    raise ValueError("영상의 시각과 FPS를 읽을 수 없습니다")
                ts = max(index / fps, previous_ts + 1.0 / fps)
            previous_ts = ts
            index += 1
            if ts - last_ts + 1e-9 < min_gap:
                continue
            last_ts = ts
            yield Frame(image=image, ts=ts)
    finally:
        cap.release()
