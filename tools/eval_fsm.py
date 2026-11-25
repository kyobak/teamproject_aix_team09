"""상태 머신 안전 지표: 검출기 출력을 실제 상태 머신(SignalFSM)에 넣었을 때 사용자가 듣게 될 안내를 채점한다 (#15).

    python tools/eval_fsm.py --videos data/phone --detector d0 --out data/fsm-d0.json

eval_signal.py 는 프레임마다 색을 맞혔는지 본다. 이 스크립트는 그 뒤, 상태 머신이 낸 상태를 본다.
정답 파일·프레임 간격(--step)·정답이 바뀌는 순간 제외 규칙은 eval_signal.py 와 같다.

지표
1. 위험 CROSS: 정답이 빨강(red)이거나 점멸(blink)인데 상태가 CROSS 인 프레임 수와,
   그런 구간으로 CROSS 가 새로 시작된 횟수(안내 "건널 수 있습니다"가 실제로 나간 횟수). 0 이어야 한다.
2. 초록→CROSS 지연: 정답이 빨강에서 초록으로 바뀐 순간부터 상태가 처음 CROSS 가 된 순간까지의 초.
   정답은 1초 단위라 ±1초 오차가 있다. 그 초록 구간 안에 CROSS 가 한 번도 안 나오면 '놓침'으로 센다.
3. UNKNOWN 비율: 평가 프레임 중 상태가 UNKNOWN 인 비율 (정답 상태별로도).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.eval_signal import DEFAULT_GT, load_labels, truth_at  # noqa: E402

DANGER = ("red", "blink")


def red_to_green_starts(states: dict[int, str]) -> list[tuple[int, int]]:
    """정답이 빨강 → 초록으로 바뀐 (시작 초, 끝 초). 끝 = 초록이 이어진 마지막 초."""
    segments = []
    for sec in sorted(states):
        if states[sec] == "green" and states.get(sec - 1) == "red":
            end = sec
            while states.get(end + 1) == "green":
                end += 1
            segments.append((sec, end))
    return segments


def evaluate_fsm_clip(path: Path, clip: dict, detector, fsm, step: int) -> dict:
    """한 영상의 상태 머신 지표. 반환값은 JSON 으로 저장할 수 있는 dict."""
    from walkaid.logic.signal_fsm import State

    states, _ = load_labels(clip)
    segments = red_to_green_starts(states)
    first_cross: dict[int, float] = {}  # 초록 시작 초 -> 처음 CROSS 가 된 시각
    by_truth: Counter = Counter()  # (정답, 상태) -> 프레임 수
    danger_frames = 0
    danger_events = 0
    prev_state = None

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"영상을 열 수 없습니다: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    index = 0
    try:
        while cap.grab():
            if index % step == 0:
                ok, image = cap.retrieve()
                ts = index / fps
                if not ok:
                    index += 1
                    continue
                state = fsm.update(detector.detect(image, ts))
                truth = truth_at(index, states)
                if truth is not None:
                    by_truth[(truth, state.value)] += 1
                    if truth in DANGER and state == State.CROSS:
                        danger_frames += 1
                        if prev_state != State.CROSS:
                            danger_events += 1
                if state == State.CROSS:
                    for start, end in segments:
                        if start <= ts < end + 1 and start not in first_cross:
                            first_cross[start] = ts
                prev_state = state
            index += 1
    finally:
        cap.release()

    delays = [round(first_cross[start] - start, 2) for start, _ in segments if start in first_cross]
    return {
        "frames": sum(by_truth.values()),
        "by_truth": {f"{t}|{s}": n for (t, s), n in sorted(by_truth.items())},
        "danger_cross_frames": danger_frames,
        "danger_cross_events": danger_events,
        "green_segments": len(segments),
        "cross_delays_sec": delays,
        "missed_cross": len(segments) - len(delays),
    }


def merge(results: list[dict]) -> dict:
    by_truth: Counter = Counter()
    for r in results:
        by_truth.update(r["by_truth"])
    frames = sum(by_truth.values())
    unknown = sum(n for key, n in by_truth.items() if key.endswith("|UNKNOWN"))
    delays = [d for r in results for d in r["cross_delays_sec"]]
    per_truth = {}
    for truth in ("red", "green", "blink", "off"):
        total = sum(n for key, n in by_truth.items() if key.startswith(f"{truth}|"))
        if total:
            per_truth[truth] = round(by_truth[f"{truth}|UNKNOWN"] / total, 4)
    return {
        "frames": frames,
        "danger_cross_frames": sum(r["danger_cross_frames"] for r in results),
        "danger_cross_events": sum(r["danger_cross_events"] for r in results),
        "green_segments": sum(r["green_segments"] for r in results),
        "missed_cross": sum(r["missed_cross"] for r in results),
        "cross_delay_median_sec": statistics.median(delays) if delays else None,
        "cross_delay_max_sec": max(delays) if delays else None,
        "unknown_ratio": round(unknown / frames, 4) if frames else None,
        "unknown_ratio_by_truth": per_truth,
    }


def print_summary(detector_name: str, step: int, total: dict) -> None:
    print(f"검출기 {detector_name} · {step}프레임마다 · 상태 머신 지표")
    print(f"  평가 프레임 {total['frames']}")
    danger, events = total["danger_cross_frames"], total["danger_cross_events"]
    print(f"  위험 CROSS (빨강·점멸 중) {danger}프레임 · 새로 시작 {events}회")
    print(
        f"  초록→CROSS 지연 중앙 {total['cross_delay_median_sec']}초 · 최대 {total['cross_delay_max_sec']}초 "
        f"(빨강→초록 {total['green_segments']}번 중 놓침 {total['missed_cross']}번, 정답 1초 단위)"
    )
    print(f"  UNKNOWN 비율 {total['unknown_ratio']} · 정답별 {total['unknown_ratio_by_truth']}")


def main(argv: list[str] | None = None) -> int:
    from walkaid.io.config import load_config
    from walkaid.logic.detector import make_detector
    from walkaid.logic.signal_fsm import SignalFSM

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--videos", type=Path, required=True, help="정답 파일에 적힌 영상이 들어 있는 폴더")
    parser.add_argument("--detector", default="d0", help="make_detector 이름 (d0, d1, d2)")
    parser.add_argument("--gt", type=Path, default=DEFAULT_GT)
    parser.add_argument("--step", type=int, default=3, help="몇 프레임마다 평가할지 (기본 3 = 초당 10장)")
    parser.add_argument("--out", type=Path, help="결과를 JSON 으로도 저장")
    args = parser.parse_args(argv)

    gt = json.loads(args.gt.read_text(encoding="utf-8"))
    config = load_config()
    per_clip: dict[str, dict] = {}
    for clip in gt["clips"]:
        path = args.videos / clip["file"]
        if not path.exists():
            print(f"건너뜀(영상 없음): {clip['file']}")
            continue
        detector = make_detector(args.detector, config)  # 영상마다 새로 (추적·상태 초기화)
        per_clip[clip["file"]] = evaluate_fsm_clip(path, clip, detector, SignalFSM(config), args.step)

    if not per_clip:
        print("평가한 영상이 없습니다. --videos 경로를 확인하세요.")
        return 1
    total = merge(list(per_clip.values()))
    print_summary(args.detector, args.step, total)
    print(f"  평가한 영상 {len(per_clip)}/{len(gt['clips'])}개")
    for name, r in per_clip.items():
        danger, delays, missed = r["danger_cross_frames"], r["cross_delays_sec"], r["missed_cross"]
        print(f"  - {name}: 위험 CROSS {danger} · 지연 {delays} · 놓침 {missed}")
    if args.out:
        args.out.write_text(json.dumps({"total": total, "clips": per_clip}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
