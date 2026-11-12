"""공식 OpenCV Zoo YuNet 모델을 받아 SHA-256을 확인한다."""

import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path

URL = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
DESTINATION = Path(__file__).resolve().parents[1] / "models" / "face_detection_yunet_2023mar.onnx"


def main():
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    if DESTINATION.exists():
        if hashlib.sha256(DESTINATION.read_bytes()).hexdigest() != SHA256:
            raise RuntimeError("기존 모델의 SHA-256이 다릅니다. 다른 경로로 보관한 뒤 다시 실행하세요.")
        print(DESTINATION)
        return
    with urllib.request.urlopen(URL, timeout=60) as response:
        content = response.read()
    if hashlib.sha256(content).hexdigest() != SHA256:
        raise RuntimeError("다운로드한 모델의 SHA-256이 다릅니다.")
    descriptor, temporary = tempfile.mkstemp(dir=DESTINATION.parent, suffix=".download")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.replace(temporary, DESTINATION)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print(DESTINATION)


if __name__ == "__main__":
    main()
