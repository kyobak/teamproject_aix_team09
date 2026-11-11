"""실행 진입점: 영상 → 검출 → SceneState → 상태 머신 → 안내 (Walking Skeleton, #9)."""

from __future__ import annotations

import argparse

from walkaid.io.camera_source import frames
from walkaid.io.config import load_config
from walkaid.logic.detector import make_detector
from walkaid.logic.signal_fsm import SignalFSM
from walkaid.present.announcer import Announcer
from walkaid.present.debug_view import DebugView


def run(
    source: str,
    detector_name: str = "d0",
    tts: bool = False,
    max_frames: int | None = None,
    view: bool = False,
) -> list[str]:
    config = load_config()
    detector = make_detector(detector_name, config)
    fsm = SignalFSM(config)
    announcer = Announcer(use_tts=tts)
    debug_view = DebugView() if view else None
    said: list[str] = []
    stream = frames(source, max_fps=config["runtime"]["target_fps"])
    try:
        for i, frame in enumerate(stream):
            if max_frames is not None and i >= max_frames:
                break
            scene = detector.detect(frame.image, frame.ts)
            state = fsm.update(scene)
            text = announcer.announce(state)
            if text:
                print(f"[{frame.ts:6.2f}s] {state.value}: {text}")
                said.append(text)
            # 박스는 SceneState 에 없으므로 검출기의 디버그용 값을 넘긴다 (없는 검출기면 None)
            if debug_view is not None and not debug_view.show(
                frame.image, scene, state, getattr(detector, "last_box", None)
            ):
                break  # 창에서 q / Esc
    finally:
        stream.close()
        if debug_view is not None:
            debug_view.close()
    return said


def main() -> None:
    p = argparse.ArgumentParser(description="시각장애인 보행 도우미")
    p.add_argument("--source", required=True, help="영상 파일 경로 또는 웹캠 번호(예: 0)")
    p.add_argument("--detector", default="d0", choices=["d0", "d1", "d2"])
    p.add_argument("--tts", action="store_true", help="음성으로 안내")
    p.add_argument("--view", action="store_true", help="시연용 디버그 화면 (q 또는 Esc 로 종료)")
    args = p.parse_args()
    run(args.source, args.detector, args.tts, view=args.view)


if __name__ == "__main__":
    main()
