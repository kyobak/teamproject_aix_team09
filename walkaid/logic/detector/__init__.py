"""검출기 선택. 검출 방법(D0/D1/D2)은 이 패키지 안에 감춘다."""

from walkaid.logic.detector.base import Detector
from walkaid.logic.detector.opencv_rule import OpenCVRuleDetector


def make_detector(name: str, config: dict) -> Detector:
    if name == "d0":
        return OpenCVRuleDetector(config)
    raise ValueError(f"아직 없는 검출기입니다: {name} (d1·d2 는 #12·#13)")
