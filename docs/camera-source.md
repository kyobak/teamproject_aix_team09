# 카메라·영상 입력 (#2)

`walkaid.io.camera_source.frames(source, max_fps=None)`는 웹캠 번호 문자열
(`"0"`) 또는 영상 경로를 받아 `Frame(image, ts)`를 한 장씩 반환합니다.
`image`는 OpenCV BGR 배열이고, `ts`는 초 단위입니다. 파일은 영상 안의
시각, 웹캠은 Unix 시각을 사용하므로 두 입력의 절대 시각을 비교하지 않습니다.

`max_fps`는 출력 프레임을 건너뛰는 상한입니다. 영상 재생 속도를 늦추지
않으며, `None`이면 모든 프레임을 제공합니다. 0·음수·무한대·NaN은 거부합니다.
영상 시각이 누락되거나 멈추거나 역행하면 원본 FPS로 시각을 이어갑니다.
시각과 FPS가 모두 유효하지 않으면 오류를 내고 입력을 닫습니다.

입력을 열지 못하면 `FileNotFoundError`, 읽기가 끝나면 반복 종료입니다.
OpenCV의 `read()` 실패는 파일 끝과 구분할 수 없으므로 손상된 영상의
완전한 디코딩을 보증하지는 않습니다. 정상 종료·읽기 예외·명시적 `close()`
시 입력을 해제합니다. 도중 종료 시에는 다음처럼 사용합니다.

```python
from contextlib import closing

from walkaid.io.camera_source import frames

with closing(frames("0")) as stream:
    for frame in stream:
        # frame.image와 frame.ts를 처리한다.
        break
```

## 검증

- Python 3.11.9, OpenCV 4.12.0, 저장소 고정 버전 환경에서 전체 테스트 21개 통과.
- `tests/test_camera_source.py`: 웹캠 모의 입력과 파일의 반환 형식, 시각,
  FPS 제한, 잘못된 설정, 열기 실패, 읽기 예외, 조기 종료 시 자원 해제 검증.
- 실제 MP4 인코더로 만든 60초 합성 영상(10fps)에서 600장과 마지막 시각
  59.9초 확인. 5fps 제한 시 300장 확인. 영상은 임시 폴더에서만 생성.
- `ruff check .`, `ruff format --check .` 통과.
- - 실제 웹캠 0번에서 Frame 반환을 확인했습니다. 이미지 형식은
  (480, 640, 3), uint8이며 초 단위 시각도 함께 반환됐습니다.
