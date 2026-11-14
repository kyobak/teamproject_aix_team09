"""합성 데이터로 가림 처리와 프레임 추출을 검증한다."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from tools.blur import blur_regions, blur_video, detect_regions, load_detectors
from tools.extract_frames import extract_frames
from tools.make_sample_video import make
from walkaid.io.camera_source import frames


def test_blur_preserves_frame_count_and_unselected_pixels(tmp_path: Path, monkeypatch):
    """후보가 없는 구간에서는 아래쪽 글자도 유지되어야 한다."""
    monkeypatch.setattr("tools.blur.detect_regions", lambda image, detectors: set())
    source = make(tmp_path / "source.mp4")
    destination = tmp_path / "blurred.mp4"
    assert blur_video(source, destination, haar_only=True) == 30
    source_frames = list(frames(str(source)))
    output_frames = list(frames(str(destination)))
    assert len(source_frames) == len(output_frames) == 30
    assert output_frames[-1].ts == pytest.approx(source_frames[-1].ts, abs=0.01)
    for original, output in zip(source_frames, output_frames, strict=True):
        assert cv2.absdiff(output.image, original.image).mean() < 5
        assert output.image[210:235].std() > 5


def test_face_and_plate_boxes_expand_and_clip_at_edges():
    image = np.indices((100, 100)).sum(axis=0).astype(np.uint8) % 2 * 255
    image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    original = image.copy()

    class Detector:
        def __init__(self, box):
            self.box = box

        def detectMultiScale(self, gray, **kwargs):
            assert gray.shape == (150, 150)
            return [self.box]

    regions = detect_regions(image, [Detector((0, 0, 30, 30)), Detector((120, 120, 30, 30))])
    assert regions == {(0, 0, 30, 30), (70, 70, 100, 100)}
    blur_regions(image, regions)
    assert image[:30, :30].std() < 5
    assert image[70:, 70:].std() < 5
    assert np.array_equal(image[30:70], original[30:70])


def test_extracts_three_images_from_three_seconds(tmp_path: Path):
    """가림 처리한 3초 영상에서 사진 3장을 만든다."""
    source = make(tmp_path / "source.mp4")
    blurred = tmp_path / "blurred.mp4"
    destination = tmp_path / "frames"

    blur_video(source, blurred, haar_only=True)

    assert extract_frames(blurred, destination) == 3
    assert sorted(path.name for path in destination.iterdir()) == [
        "000001.jpg",
        "000002.jpg",
        "000003.jpg",
    ]

    for path in destination.iterdir():
        image = cv2.imread(str(path))
        assert image is not None
        assert image.shape == (240, 320, 3)


def test_blur_rejects_same_input_and_output(tmp_path: Path):
    """원본 파일을 실수로 덮어쓰지 않는다."""
    source = make(tmp_path / "source.mp4")
    original_bytes = source.read_bytes()

    with pytest.raises(ValueError):
        blur_video(source, source)

    assert source.read_bytes() == original_bytes


def test_extraction_does_not_overwrite_existing_files(tmp_path: Path):
    """추출 폴더에 기존 파일이 있으면 보존하고 중단한다."""
    source = make(tmp_path / "source.mp4")
    destination = tmp_path / "frames"
    destination.mkdir()
    existing = destination / "keep.txt"
    existing.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError):
        extract_frames(source, destination)

    assert existing.read_text(encoding="utf-8") == "keep"


def test_load_detectors_from_korean_path(tmp_path: Path, monkeypatch):
    directory = tmp_path / "한글 검출기"
    directory.mkdir()
    original = Path(cv2.data.haarcascades)
    for filename in ("haarcascade_frontalface_default.xml", "haarcascade_russian_plate_number.xml"):
        (directory / filename).write_bytes((original / filename).read_bytes())
    monkeypatch.setattr(cv2.data, "haarcascades", str(directory))
    detectors = load_detectors()
    assert len(detectors) == 2
    assert all(not detector.empty() for detector in detectors)
    gray = np.zeros((100, 100), dtype=np.uint8)
    assert all(len(detector.detectMultiScale(gray)) == 0 for detector in detectors)
