"""실행 진입점: 영상 → 검출 → SceneState → 상태 머신 → 안내 (Walking Skeleton, #9)."""

from __future__ import annotations

import argparse

from walkaid.io.camera_source import frames
from walkaid.io.config import load_config
from walkaid.logic.detector import make_detector
from walkaid.logic.signal_fsm import SignalFSM
from walkaid.present.announcer import Announcer


def run(source: str, detector_name: str = "d0", tts: bool = False, max_frames: int | None = None) -> list[str]:
    config = load_config()
    detector = make_detector(detector_name, config)
    fsm = SignalFSM(config)
    announcer = Announcer(use_tts=tts)
    said: list[str] = []
    for i, frame in enumerate(frames(source, max_fps=config["runtime"]["target_fps"])):
        if max_frames is not None and i >= max_frames:
            break
        scene = detector.detect(frame.image, frame.ts)
        state = fsm.update(scene)
        text = announcer.announce(state)
        if text:
            print(f"[{frame.ts:6.2f}s] {state.value}: {text}")
            said.append(text)
    return said


def main() -> None:
    p = argparse.ArgumentParser(description="시각장애인 보행 도우미")
    p.add_argument("--source", required=True, help="영상 파일 경로 또는 웹캠 번호(예: 0)")
    p.add_argument("--detector", default="d0", choices=["d0", "d1", "d2"])
    p.add_argument("--tts", action="store_true", help="음성으로 안내")
    args = p.parse_args()
    run(args.source, args.detector, args.tts)


if __name__ == "__main__":
    main()
