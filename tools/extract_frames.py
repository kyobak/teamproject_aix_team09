"""가림 처리한 영상에서 1초마다 사진 한 장을 추출한다."""

from __future__ import annotations

import argparse
import math
import sys
from contextlib import closing
from pathlib import Path

import cv2


def extract_frames(source: Path, destination: Path) -> int:
    """영상 시각 0초, 1초, 2초…에 해당하는 프레임을 저장한다."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from walkaid.io.camera_source import frames

    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise FileExistsError(f"출력 경로가 비어 있지 않습니다: {destination}")

    count = 0
    last_second = -1

    with closing(frames(str(source))) as stream:
        for frame in stream:
            second = math.floor(frame.ts + 1e-6)
            if second <= last_second:
                continue

            destination.mkdir(parents=True, exist_ok=True)
            path = destination / f"{count + 1:06d}.jpg"
            if not cv2.imwrite(str(path), frame.image):
                raise RuntimeError(f"사진을 저장하지 못했습니다: {path}")

            last_second = second
            count += 1

    if count == 0:
        raise ValueError("추출할 수 있는 프레임이 없습니다.")

    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    count = extract_frames(args.source, args.destination)
    print(f"완료: {count}장 → {args.destination}")


if __name__ == "__main__":
    main()
