"""웹캠과 mp4를 같은 방식으로 읽는다 (#2 에서 완성).

`frames()` 하나만 바깥에 보여 준다. 로직 계층은 입력이 웹캠인지 파일인지 모른다.
"""

from __future__ import annotations

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
    """source 가 숫자면 웹캠 번호, 아니면 영상 파일 경로로 연다."""
    cap = cv2.VideoCapture(int(source)) if source.isdigit() else cv2.VideoCapture(source)
    if not cap.isOpened():
        raise FileNotFoundError(f"입력을 열 수 없습니다: {source}")
    is_file = not source.isdigit()
    min_gap = 1.0 / max_fps if max_fps else 0.0
    last_ts = -1e9
    try:
        while True:
            ok, image = cap.read()
            if not ok:
                break
            ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0 if is_file else time.time()
            if ts - last_ts < min_gap:
                continue
            last_ts = ts
            yield Frame(image=image, ts=ts)
    finally:
        cap.release()
