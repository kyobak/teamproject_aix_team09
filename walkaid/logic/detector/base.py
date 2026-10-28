"""Detector 인터페이스 — D0(OpenCV), D1(사전학습 YOLO), D2(미세조정 YOLO)를 갈아 끼운다."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from walkaid.logic.scene_state import SceneState


class Detector(ABC):
    @abstractmethod
    def detect(self, image: np.ndarray, ts: float) -> SceneState:
        """BGR 이미지 한 장을 받아 SceneState 를 돌려준다."""
