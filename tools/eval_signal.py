"""신호 판정 평가: 정답 파일(`data/labels/signal_eval_gt.json`)로 검출기(D0·D1·D2)를 같은 조건에서 비교한다 (#15).

    python tools/eval_signal.py --videos data/phone --detector d0

- 3프레임마다 1장(초당 10장)을 검출기에 넣고, 그 프레임이 속한 1초의 정답과 비교한다.
- 정답이 바뀌는 순간 앞뒤 10프레임(약 0.3초)은 평가에서 뺀다.
- 점멸 구간(`blink_sec`)은 green·off 둘 다 맞힌 것으로 본다.
- 위치: 검출기에 `last_box`([x, y, w, h])가 있으면, 그 중심이 정답 박스 근처(가로 ±0.5칸 폭,
  세로 ±0.25칸 높이)일 때만 맞힌 것으로 센다. 다른 위치의 판정은 `red*`·`green*` 처럼 별표로 따로 센다.
  `last_box` 가 없는 검출기는 위치를 확인하지 않는다(결과 첫 줄에 표시).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GT = PROJECT_ROOT / "data" / "labels" / "signal_eval_gt.json"
NEAR_CHANGE = 10  # 프레임
EXPECTED = {"red": {"red"}, "green": {"green"}, "off": {"off"}, "blink": {"green", "off"}}


def load_labels(clip: dict) -> tuple[dict[int, str], dict[int, list[int]]]:
    """1초마다의 정답 상태와 박스. 점멸 구간의 정답은 'blink' 로 바꾼다."""
    states = {row["sec"]: row["state"] for row in clip["labels"]}
    boxes = {row["sec"]: row["box"] for row in clip["labels"]}
    if clip.get("blink_sec"):
        start, end = clip["blink_sec"]
        for sec in states:
            if start <= sec <= end:
                states[sec] = "blink"
    return states, boxes


def truth_at(index: int, states: dict[int, str]) -> str | None:
    """index 번째 프레임의 정답. 정답이 없거나 바뀌는 순간 근처면 None(평가 제외)."""
    state = states.get(index // 30)
    if state is None:
        return None
    for near in (index - NEAR_CHANGE, index + NEAR_CHANGE):
        other = states.get(near // 30)
        if other is not None and other != state:
            return None
    return state


def near_box(pred: list[int] | None, truth: list[int]) -> bool:
    if not pred:
        return False
    x, y, w, h = truth
    cx, cy = pred[0] + pred[2] / 2, pred[1] + pred[3] / 2
    return x - 0.5 * w <= cx <= x + 1.5 * w and y - 0.25 * h <= cy <= y + 1.25 * h


def judge(scene, detector, truth_box: list[int]) -> str:
    """판정을 'red'·'green'·'off'·'unknown'·'none' 으로, 다른 위치면 뒤에 '*'."""
    if not scene.signal.present:
        return "none"
    pred = scene.signal.color
    if not hasattr(detector, "last_box") or near_box(detector.last_box, truth_box):
        return pred
    return pred + "*"


def longest_runs(sequence: list[bool]) -> int:
    best = run = 0
    for hit in sequence:
        run = run + 1 if hit else 0
        best = max(best, run)
    return best


def evaluate_clip(path: Path, clip: dict, detector, step: int) -> tuple[Counter, int]:
    """정답 상태별 판정 개수와, 빨간불인데 green(같은 위치)이 가장 길게 이어진 프레임 수."""
    states, boxes = load_labels(clip)
    counts: Counter = Counter()
    red_green: list[bool] = []
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"영상을 열 수 없습니다: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    index = 0
    try:
        while cap.grab():
            if index % step == 0:
                ok, image = cap.retrieve()
                scene = detector.detect(image, index / fps) if ok else None
                truth = truth_at(index, states)
                key = None
                if scene is not None and truth is not None:
                    key = judge(scene, detector, boxes[index // 30])
                    counts[(truth, key)] += 1
                red_green.append(truth == "red" and key == "green")  # 평가 제외 프레임은 연속을 끊는다
            index += 1
    finally:
        cap.release()
    return counts, longest_runs(red_green)


def summary_rows(counts: Counter) -> list[tuple[str, int, int]]:
    rows = []
    for truth in ("red", "green", "blink", "off"):
        total = sum(n for (t, _), n in counts.items() if t == truth)
        if total:
            hit = sum(counts[(truth, key)] for key in EXPECTED[truth])
            rows.append((truth, hit, total))
    return rows


def print_report(name: str, counts: Counter) -> None:
    print(f"\n[{name}]")
    for truth, hit, total in summary_rows(counts):
        detail = {key: n for (t, key), n in sorted(counts.items(), key=lambda kv: -kv[1]) if t == truth}
        print(f"  {truth:5} {hit:5d}/{total:<5d} {hit / total:5.0%}  {detail}")


def main(argv: list[str] | None = None) -> int:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from walkaid.io.config import load_config
    from walkaid.logic.detector import make_detector

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--videos", type=Path, required=True, help="정답 파일에 적힌 영상이 들어 있는 폴더")
    parser.add_argument("--detector", default="d0", help="make_detector 이름 (d0, d1, d2)")
    parser.add_argument("--gt", type=Path, default=DEFAULT_GT)
    parser.add_argument("--step", type=int, default=3, help="몇 프레임마다 평가할지 (기본 3 = 초당 10장)")
    parser.add_argument("--out", type=Path, help="결과를 JSON 으로도 저장")
    args = parser.parse_args(argv)

    gt = json.loads(args.gt.read_text(encoding="utf-8"))
    config = load_config()
    groups: dict[str, Counter] = defaultdict(Counter)
    longest: dict[str, int] = {}
    location_checked = None
    for clip in gt["clips"]:
        path = args.videos / clip["file"]
        if not path.exists():
            print(f"건너뜀(영상 없음): {clip['file']}")
            continue
        detector = make_detector(args.detector, config)  # 영상마다 새로 (추적 상태 초기화)
        location_checked = hasattr(detector, "last_box")
        counts, run = evaluate_clip(path, clip, detector, args.step)
        longest[clip["file"]] = run
        for group in ("전체", f"장소 {clip['place']}", clip["split"], clip["lighting"], clip["file"]):
            groups[group].update(counts)

    if location_checked is None:
        print("평가한 영상이 없습니다. --videos 경로를 확인하세요.")
        return 1
    print(f"검출기 {args.detector} · {args.step}프레임마다 · 위치 확인 {'함' if location_checked else '안 함'}")
    for name in ["전체", "dev", "test", "day", "dusk", "night"] + sorted(k for k in groups if k.startswith("장소")):
        if name in groups:
            print_report(name, groups[name])
    total = groups["전체"]
    print("\n[안전]")
    print(f"  빨간불인데 green (같은 위치) {total[('red', 'green')]} · 다른 위치 {total[('red', 'green*')]}")
    print(f"  빨간불인데 green 최장 연속 {max(longest.values())}프레임")
    print(f"  점멸 중 off {total[('blink', 'off')]} / {sum(n for (t, _), n in total.items() if t == 'blink')}")
    for name in sorted(k for k in groups if k.endswith(".mp4")):
        print_report(name, groups[name])

    if args.out:
        result = {name: {f"{t}|{k}": n for (t, k), n in c.items()} for name, c in groups.items()}
        args.out.write_text(json.dumps({"counts": result, "longest_red_green": longest}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
