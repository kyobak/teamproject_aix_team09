"""팀원 환경 점검: python tools/check_env.py 가 'OK' 로 끝나면 같은 환경입니다."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REQUIRED = {"numpy": "2.2.6", "cv2": "4.12.0", "yaml": "6.0.2"}


def main() -> int:
    ok = True
    if sys.version_info[:2] != (3, 11):
        print(f"[X] Python 3.11 이 필요합니다 (지금 {sys.version.split()[0]})")
        ok = False
    else:
        print(f"[O] Python {sys.version.split()[0]}")
    for mod, want in REQUIRED.items():
        try:
            m = __import__(mod)
            have = getattr(m, "__version__", "?")
            mark = "O" if have.startswith(want) else "X"
            ok &= mark == "O"
            print(f"[{mark}] {mod} {have} (기대 {want})")
        except ImportError:
            print(f"[X] {mod} 가 설치되지 않았습니다 → pip install -r requirements-dev.txt")
            ok = False
    if ok:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from tools.make_sample_video import make
        from walkaid.main import run

        with tempfile.TemporaryDirectory() as d:
            said = run(str(make(Path(d) / "s.mp4")))
        ok &= bool(said)
        print(f"[{'O' if said else 'X'}] 파이프라인 실행 (안내 {len(said)}건)")
    print("OK" if ok else "FAIL — README 의 '환경 맞추기'를 다시 확인하세요")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
