"""Haar와 YuNet으로 얼굴·번호판을 찾아 넓게 흐린다."""

from __future__ import annotations

import argparse
import math
import sys
from collections import deque
from contextlib import closing
from pathlib import Path

import cv2
import numpy as np

DEFAULT_YUNET_MODEL = Path(__file__).resolve().parents[1] / "models" / "face_detection_yunet_2023mar.onnx"


def load_detectors():
    detectors = []
    for filename in ("haarcascade_frontalface_default.xml", "haarcascade_russian_plate_number.xml"):
        xml = (Path(cv2.data.haarcascades) / filename).read_text(encoding="utf-8")
        storage = cv2.FileStorage(xml, cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)
        try:
            detector = cv2.CascadeClassifier()
            if not detector.read(storage.getFirstTopLevelNode()) or detector.empty():
                raise RuntimeError(f"검출기를 열 수 없습니다: {filename}")
        finally:
            storage.release()
        detectors.append(detector)
    return detectors


def load_yunet(model_path: Path = DEFAULT_YUNET_MODEL, score_threshold: float = 0.75):
    if not 0 < score_threshold <= 1:
        raise ValueError("YuNet 신뢰도는 0보다 크고 1 이하여야 합니다.")
    if not model_path.is_file():
        raise FileNotFoundError(f"YuNet 모델이 없습니다: {model_path}. python tools/download_yunet.py를 실행하세요.")
    # ONNX도 메모리에서 읽어 한글 경로를 지원한다.
    model = np.frombuffer(model_path.read_bytes(), dtype=np.uint8)
    try:
        return cv2.FaceDetectorYN.create(
            "onnx", model, np.empty(0, dtype=np.uint8), (320, 320), score_threshold, 0.3, 5000
        )
    except cv2.error as error:
        raise RuntimeError(f"YuNet 모델을 읽을 수 없습니다: {model_path}") from error


def expanded_region(x, y, width, height, image_width, image_height):
    if not all(math.isfinite(v) for v in (x, y, width, height)) or width <= 0 or height <= 0:
        return None
    left = max(0, math.floor(x - width * 0.5))
    top = max(0, math.floor(y - height * 0.5))
    right = min(image_width, math.ceil(x + width * 1.5))
    bottom = min(image_height, math.ceil(y + height * 1.5))
    if left >= right or top >= bottom:
        return None
    return left, top, right, bottom


def detect_regions(image, detectors):
    scale = 1.5
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(cv2.resize(gray, None, fx=scale, fy=scale))
    height, width = image.shape[:2]
    regions = set()
    for detector in detectors:
        for x, y, w, h in detector.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=50):
            region = expanded_region(x / scale, y / scale, w / scale, h / scale, width, height)
            if region is not None:
                regions.add(region)
    return regions


def detect_yunet_regions(image, detector):
    height, width = image.shape[:2]
    detector.setInputSize((width, height))
    _, faces = detector.detect(image)
    regions = set()
    if faces is not None:
        for face in faces:
            region = expanded_region(*(float(v) for v in face[:4]), width, height)
            if region is not None:
                regions.add(region)
    return regions


def blur_regions(image, regions):
    for left, top, right, bottom in sorted(regions):
        roi = image[top:bottom, left:right]
        height, width = roi.shape[:2]
        small = cv2.resize(roi, (min(6, width), min(6, height)), interpolation=cv2.INTER_AREA)
        smooth = cv2.GaussianBlur(small, (0, 0), sigmaX=1.6)
        roi[:] = cv2.resize(smooth, (width, height), interpolation=cv2.INTER_LINEAR)


def blur_video(
    source: Path,
    destination: Path,
    *,
    yunet_model: Path = DEFAULT_YUNET_MODEL,
    score_threshold: float = 0.75,
    haar_only: bool = False,
    protected_regions=(),
) -> int:
    """매 프레임에서 두 얼굴 검출기의 결과와 Haar 번호판 결과를 합친다."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from walkaid.io.camera_source import frames

    if source.resolve() == destination.resolve():
        raise ValueError("입력과 출력 경로는 달라야 합니다.")
    if destination.exists():
        raise FileExistsError(f"출력 파일이 이미 있습니다: {destination}")
    for left, top, right, bottom in protected_regions:
        if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
            raise ValueError("보존 영역은 0~1 범위의 left top right bottom 순서여야 합니다.")

    capture = cv2.VideoCapture(str(source))
    try:
        if not capture.isOpened():
            raise FileNotFoundError(f"입력을 열 수 없습니다: {source}")
        fps = capture.get(cv2.CAP_PROP_FPS)
    finally:
        capture.release()
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("영상의 FPS를 읽을 수 없습니다.")

    detectors = load_detectors()
    yunet = None if haar_only else load_yunet(yunet_model, score_threshold)
    destination.parent.mkdir(parents=True, exist_ok=True)
    recent = deque(maxlen=3)
    writer = None
    count = 0
    try:
        with closing(frames(str(source))) as stream:
            for frame in stream:
                image = frame.image.copy()
                height, width = image.shape[:2]
                if writer is None:
                    writer = cv2.VideoWriter(str(destination), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
                    if not writer.isOpened():
                        raise RuntimeError("출력 영상을 만들 수 없습니다.")
                regions = detect_regions(image, detectors)
                if yunet is not None:
                    regions.update(detect_yunet_regions(image, yunet))
                recent.append(regions)
                blur_regions(image, set().union(*recent))
                # 사용자 지정 신호등 영역은 흐림 전에 읽은 원본 픽셀로 복원한다.
                for left, top, right, bottom in protected_regions:
                    x1, y1 = math.floor(left * width), math.floor(top * height)
                    x2, y2 = math.ceil(right * width), math.ceil(bottom * height)
                    image[y1:y2, x1:x2] = frame.image[y1:y2, x1:x2]
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
    parser.add_argument("--yunet-model", type=Path, default=DEFAULT_YUNET_MODEL)
    parser.add_argument("--score-threshold", type=float, default=0.75)
    parser.add_argument("--haar-only", action="store_true", help="비교를 위해 기존 Haar만 사용")
    parser.add_argument(
        "--protect",
        type=float,
        nargs=4,
        action="append",
        default=[],
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        help="신호등 보존 영역, 각 좌표는 0~1",
    )
    args = parser.parse_args()
    count = blur_video(
        args.source,
        args.destination,
        yunet_model=args.yunet_model,
        score_threshold=args.score_threshold,
        haar_only=args.haar_only,
        protected_regions=args.protect,
    )
    print(f"완료: {count}프레임 → {args.destination}")


if __name__ == "__main__":
    main()
