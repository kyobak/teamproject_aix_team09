# 시각장애인 보행 도우미 — 굳건 팀 (AI+X 공학융합프로젝트 2026 가을)

카메라 영상에서 보행 신호등과 점자블록을 인식해, 횡단보도에서 **건너도 되는지를 음성·진동으로 알려 주는** 보조 도구입니다.
확실하지 않으면 "판단할 수 없습니다"라고 말하고, 절대 함부로 "건널 수 있습니다"를 내지 않는 것이 설계 원칙입니다.

> 팀원: 박재원 · 박지성 · 강태혁 · 전시준

## 구조

```
카메라/영상 → [walkaid/io] → 검출기 D0·D1·D2 [walkaid/logic/detector] → SceneState
           → 상태 머신 [walkaid/logic/signal_fsm.py] → 음성·진동 [walkaid/present]
```

| 계층 | 폴더 | 의존하지 않는 것 |
|---|---|---|
| 표현 | `walkaid/present/` | 검출 방법, HSV 값, 입력 종류 |
| 로직 | `walkaid/logic/` | 안내 방식, 카메라 장치, 라벨링 도구 |
| 데이터 | `walkaid/io/`, `config.yaml`, `data/`, `models/` | 상태 머신 규칙, 안내 문구 |

모듈 사이는 `SceneState`(`walkaid/logic/scene_state.py`) 하나로만 주고받습니다. 자세한 설계는 [`docs/week-07.md`](docs/week-07.md).

## 환경 맞추기 (모든 팀원 동일)

Python **3.11** + 고정 버전 패키지(`requirements.txt`)를 씁니다.

```bash
git clone https://github.com/kyobak/teamproject_aix_team09.git
cd teamproject_aix_team09

# 1) Python 3.11 가상환경
python3.11 -m venv .venv            # Windows: py -3.11 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate

# 2) 패키지 설치
pip install -r requirements-dev.txt

# 3) 점검 — 마지막 줄이 OK 면 같은 환경입니다
python tools/check_env.py
```

Python 3.11 이 없으면: macOS `brew install python@3.11`, Windows [python.org](https://www.python.org/downloads/) 에서 3.11.x 설치.

## 실행

```bash
python tools/make_sample_video.py                         # data/sample.mp4 생성 (합성 영상)
python -m walkaid.main --source data/sample.mp4           # 영상 파일
python -m walkaid.main --source 0 --tts                   # 웹캠 + 음성
```

## 테스트

```bash
pytest          # 단위 테스트
ruff check .    # 문법·스타일
```

PR 마다 GitHub Actions 가 같은 검사를 돌립니다.

## 협업 규칙

브랜치·커밋·PR·리뷰·머지 규칙은 [`CONTRIBUTING.md`](CONTRIBUTING.md), 팀 규칙은 [`docs/team-rules.md`](docs/team-rules.md).
AI 사용 기록은 [`PROMPTS.md`](PROMPTS.md), 윤리적 판단은 [`ETHICS.md`](ETHICS.md).

## 데이터와 개인정보

영상·이미지·모델 가중치는 저장소에 올리지 않습니다(`.gitignore`). 블러 처리된 데이터만 팀 공유 드라이브에 둡니다.
실시간 카메라 프레임은 판단 후 바로 버립니다.

## 라이선스·출처

- OpenCV (Apache-2.0)
- Ultralytics YOLO 를 D1·D2 에서 쓸 예정 (AGPL-3.0) — 도입 시 여기에 추가
