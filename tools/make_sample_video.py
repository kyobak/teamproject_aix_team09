"""환경 점검용 3초짜리 합성 영상을 만든다 (사람·실제 장소 없음).

사용: python tools/make_sample_video.py  → data/sample.mp4
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np


def make(path: Path, seconds: int = 3, fps: int = 10) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (320, 240))
    for i in range(seconds * fps):
        img = np.full((240, 320, 3), 40, np.uint8)
        cv2.putText(img, f"frame {i}", (10, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        out.write(img)
    out.release()
    return path


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/sample.mp4")
    print(make(target))
