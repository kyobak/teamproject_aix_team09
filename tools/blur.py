"""Haar 검출기로 찾은 얼굴과 번호판 주변을 강하게 흐린다."""

from __future__ import annotations

import argparse
import math
import sys
from collections import deque
from contextlib import closing
from pathlib import Path

import cv2


def load_detectors():
    detectors = []
    for filename in ("haarcascade_frontalface_default.xml", "haarcascade_russian_plate_number.xml"):
        detector = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / filename))
        if detector.empty():
            raise RuntimeError(f"검출기를 열 수 없습니다: {filename}")
        detectors.append(detector)
    return detectors


def detect_regions(image, detectors):
    # 작은 얼굴/번호판이 검출 창 크기에 들어오도록 확대한다.
    scale = 1.5
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(cv2.resize(gray, None, fx=scale, fy=scale))
    height, width = image.shape[:2]
    regions = set()
    for detector in detectors:
        for x, y, w, h in detector.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=3):
            # 양쪽으로 각각 검출 폭/높이의 절반만큼 더 가린다.
            left = max(0, math.floor((x - w * 0.5) / scale))
            top = max(0, math.floor((y - h * 0.5) / scale))
            right = min(width, math.ceil((x + w * 1.5) / scale))
            bottom = min(height, math.ceil((y + h * 1.5) / scale))
            regions.add((left, top, right, bottom))
    return regions


def blur_regions(image, regions):
    for left, top, right, bottom in sorted(regions):
        roi = image[top:bottom, left:right]
        height, width = roi.shape[:2]
        # 몇 개의 색 표본만 남기고 부드럽게 확대해 세부 윤곽을 흐린다.
        small = cv2.resize(roi, (min(6, width), min(6, height)), interpolation=cv2.INTER_AREA)
        smooth = cv2.GaussianBlur(small, (0, 0), sigmaX=1.6)
        roi[:] = cv2.resize(smooth, (width, height), interpolation=cv2.INTER_LINEAR)


def blur_video(source: Path, destination: Path) -> int:
    """원본을 보존하고 가린 영상을 별도 파일로 저장한다."""
    # python tools/blur.py로 실행해도 프로젝트 모듈을 찾도록 한다.
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from walkaid.io.camera_source import frames

    if source.resolve() == destination.resolve():
        raise ValueError("입력과 출력 경로는 달라야 합니다.")
    if destination.exists():
        raise FileExistsError(f"출력 파일이 이미 있습니다: {destination}")

    capture = cv2.VideoCapture(str(source))
    try:
        if not capture.isOpened():
            raise FileNotFoundError(f"입력을 열 수 없습니다: {source}")
        fps = capture.get(cv2.CAP_PROP_FPS)
    finally:
        capture.release()

    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("영상의 FPS를 읽을 수 없습니다.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    detectors = load_detectors()
    recent = deque(maxlen=3)
    writer = None
    count = 0

    try:
        with closing(frames(str(source))) as stream:
            for frame in stream:
                image = frame.image.copy()
                height, width = image.shape[:2]

                if writer is None:
                    writer = cv2.VideoWriter(
                        str(destination),
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        fps,
                        (width, height),
                    )
                    if not writer.isOpened():
                        raise RuntimeError("출력 영상을 만들 수 없습니다.")

                recent.append(detect_regions(image, detectors))
                blur_regions(image, set().union(*recent))
                writer.write(image)
                count += 1
    finally:
        if writer is not None:
            writer.release()

    if count == 0:
        raise ValueError("읽을 수 있는 프레임이 없습니다.")

    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    count = blur_video(args.source, args.destination)
    print(f"완료: {count}프레임 → {args.destination}")


if __name__ == "__main__":
    main()
