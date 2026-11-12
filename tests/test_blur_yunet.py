"""YuNet은 합성 데이터와 모의 검출기로 검증한다. 모델 다운로드가 없어도 실행한다."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from tools import blur
from tools.make_sample_video import make
from walkaid.io.camera_source import frames


def test_yunet_resizes_input_and_combines_with_haar(tmp_path: Path, monkeypatch):
    source = tmp_path / "pattern.mp4"
    destination = tmp_path / "combined.mp4"
    rows, columns = np.indices((240, 320))
    gray = (((rows // 4 + columns // 4) % 2) * 255).astype(np.uint8)
    image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    assert writer.isOpened()
    for _ in range(4):
        writer.write(image)
    writer.release()

    class YuNet:
        def __init__(self):
            self.sizes = []

        def setInputSize(self, size):
            self.sizes.append(size)

        def detect(self, image):
            return 1, np.array([[240, 20, 20, 20, *([0] * 10), 0.95]], dtype=np.float32)

    yunet = YuNet()
    monkeypatch.setattr(blur, "load_yunet", lambda path, threshold: yunet)
    monkeypatch.setattr(blur, "load_detectors", lambda: [])
    candidates = iter([{(0, 0, 50, 50)}, set(), set(), set()])
    monkeypatch.setattr(blur, "detect_regions", lambda image, detectors: next(candidates))
    recorded = []
    apply_blur = blur.blur_regions

    def record_blur(image, regions):
        recorded.append(regions)
        apply_blur(image, regions)

    monkeypatch.setattr(blur, "blur_regions", record_blur)
    assert blur.blur_video(source, destination, protected_regions=[(0, 0, 0.25, 0.5)]) == 4
    assert yunet.sizes == [(320, 240)] * 4
    # Haar와 YuNet 한쪽에서만 찾은 후보도 남기고 직전 두 프레임을 유지한다.
    assert all(regions == {(0, 0, 50, 50), (230, 10, 270, 50)} for regions in recorded[:3])
    assert recorded[3] == {(230, 10, 270, 50)}
    original = list(frames(str(source)))
    output = list(frames(str(destination)))
    for before, after in zip(original, output, strict=True):
        assert cv2.absdiff(before.image[:120, :80], after.image[:120, :80]).mean() < 5
        assert after.image[15:45, 235:265].std() < before.image[15:45, 235:265].std() * 0.2


def test_yunet_handles_no_faces_and_rejects_invalid_boxes():
    class YuNet:
        def setInputSize(self, size):
            assert size == (80, 100)

        def detect(self, image):
            return 1, None

    assert blur.detect_yunet_regions(np.zeros((100, 80, 3), dtype=np.uint8), YuNet()) == set()
    assert blur.expanded_region(float("nan"), 0, 10, 10, 80, 100) is None
    assert blur.expanded_region(500, 500, 10, 10, 80, 100) is None
    assert blur.expanded_region(0, 0, -1, 10, 80, 100) is None


def test_yunet_loads_model_bytes_from_korean_path(tmp_path: Path, monkeypatch):
    model = tmp_path / "한글 모델.onnx"
    model.write_bytes(b"fake-model-for-loader-test")
    sentinel = object()

    def create(framework, weights, config, size, score, nms, top_k):
        assert framework == "onnx"
        assert weights.tobytes() == model.read_bytes()
        assert config.size == 0
        assert size == (320, 320)
        assert (score, nms, top_k) == (0.75, 0.3, 5000)
        return sentinel

    monkeypatch.setattr(cv2.FaceDetectorYN, "create", create)
    assert blur.load_yunet(model) is sentinel


@pytest.mark.parametrize("score", [0, -1, 1.1, float("nan"), float("inf")])
def test_invalid_yunet_score_is_rejected(tmp_path: Path, score):
    with pytest.raises(ValueError):
        blur.load_yunet(tmp_path / "absent.onnx", score)


def test_missing_yunet_model_does_not_silently_fall_back(tmp_path: Path):
    source = make(tmp_path / "source.mp4")
    output = tmp_path / "output.mp4"
    with pytest.raises(FileNotFoundError, match="YuNet"):
        blur.blur_video(source, output, yunet_model=tmp_path / "absent.onnx")
    assert not output.exists()


def test_invalid_protection_is_rejected_before_opening_video(tmp_path: Path):
    with pytest.raises(ValueError, match="보존"):
        blur.blur_video(tmp_path / "absent.mp4", tmp_path / "out.mp4", protected_regions=[(0.9, 0, 0.1, 1)])
