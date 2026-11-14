"""실행 진입점: 영상 → 검출 → SceneState → 상태 머신 → 안내 (Walking Skeleton, #9)."""

from __future__ import annotations

import argparse
import time

from walkaid.io.camera_source import frames
from walkaid.io.config import load_config
from walkaid.logic.detector import make_detector
from walkaid.logic.signal_fsm import SignalFSM
from walkaid.present.announcer import Announcer


def run(
    source: str,
    detector_name: str = "d0",
    tts: bool = False,
    max_frames: int | None = None,
    realtime: bool | None = None,
) -> list[str]:
    """영상 → 판단 → 안내.

    realtime: 영상 파일을 실제 속도로 재생할지 (#34). None 이면 '음성을 켜고 영상 파일을 넣었을 때'만 켠다.
    영상 파일은 실제보다 훨씬 빨리 처리되므로, 실제 속도로 맞추지 않으면 안내가 서로 덮어써서 끊긴다.
    웹캠은 원래 실제 속도라 맞출 필요가 없다.
    """
    config = load_config()
    detector = make_detector(detector_name, config)
    fsm = SignalFSM(config)
    announcer = Announcer(use_tts=tts)
    if realtime is None:
        realtime = tts and not source.isdigit()
    said: list[str] = []
    start_wall: float | None = None
    start_ts = 0.0
    try:
        for i, frame in enumerate(frames(source, max_fps=config["runtime"]["target_fps"])):
            if max_frames is not None and i >= max_frames:
                break
            if realtime:
                if start_wall is None:
                    start_wall, start_ts = time.monotonic(), frame.ts
                ahead = (frame.ts - start_ts) - (time.monotonic() - start_wall)
                if ahead > 0:
                    time.sleep(ahead)  # 영상 속 시각을 따라잡을 때까지 기다린다
            scene = detector.detect(frame.image, frame.ts)
            state = fsm.update(scene)
            text = announcer.announce(state)
            if text:
                print(f"[{frame.ts:6.2f}s] {state.value}: {text}")
                said.append(text)
        announcer.wait_idle()  # 마지막 안내를 끝까지 말한 뒤 끝낸다
    finally:
        announcer.close()
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
