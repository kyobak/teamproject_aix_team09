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

## 휴대폰 카메라 HTTPS 프레임 서버 (#44)

노트북에서 검출기와 상태 머신을 실행합니다. 같은 Wi-Fi의 휴대폰 웹앱은 JPEG를 보내고 신호 상태를 받아 안내합니다. 같은 주소에서 #45의 웹앱을 열려면 `--web-dir`에 웹앱 빌드 폴더를 지정하세요.

1. 노트북의 Wi-Fi IPv4 주소를 확인합니다(Windows는 `ipconfig`). 아래 `192.168.1.20`을 그 주소로 바꿉니다.
2. 개발용 로컬 CA와 서버 인증서를 만듭니다. 예시는 [mkcert](https://github.com/FiloSottile/mkcert) 사용법입니다.

```powershell
$lan = "192.168.1.20"
New-Item -ItemType Directory -Force data/tls | Out-Null
mkcert -install
mkcert -cert-file data/tls/server.pem -key-file data/tls/server-key.pem localhost 127.0.0.1 $lan
```

3. 안드로이드의 인증서 설정에서 `mkcert -CAROOT` 아래 **공개 CA 인증서 `rootCA.pem`만** 신뢰하도록 설치합니다. `rootCA-key.pem`과 서버 개인키는 노트북에 둡니다. Chrome에서 접속 주소의 인증서가 유효한지 확인한 뒤 카메라를 허용합니다. 노트북 방화벽에서 필요할 때만 시연용 사설 네트워크에서 지정 포트를 허용합니다.

```powershell
& "..\.venv\Scripts\python.exe" -X utf8 -m walkaid.frame_server --host $lan --port 8443 --detector d0 --cert data/tls/server.pem --key data/tls/server-key.pem
```

웹앱 시험 시 위 명령에 `--web-dir <웹앱-폴더>`를 추가하고, 휴대폰 Chrome에서 `https://192.168.1.20:8443/`을 엽니다. 인증서 생성에 사용한 실제 IP로 접속합니다. 노트북 선택 포트가 이미 사용 중이면 인증서는 그대로 두고 포트만 바꿀 수 있습니다. `--detector d1`은 #12의 검출기와 모델이 있는 환경, `d2`는 팩토리에 D2가 등록된 환경에서 실행합니다.

#45 웹앱 없이 서버만 시험하려면 같은 실행 명령에 `--web-dir tools/frame_server_probe`를 붙입니다. 폰에서 같은 HTTPS 주소를 열고 **카메라 검사 시작**을 누르면 JPEG 30장의 왕복 시간과 입력 중단 후 상태가 표시됩니다.

### 웹앱 API

- `POST /api/frame`: 요청 본문은 JPEG 바이트, `Content-Type: image/jpeg`. 응답은 `{"state":"WAIT"}` 같은 JSON입니다. 상태는 `NO_SIGNAL`, `WAIT`, `CROSS`, `BLINK`, `UNKNOWN` 중 하나입니다.
- `GET /api/status`: 해당 스트림의 현재 상태를 반환합니다. 유효한 프레임이 1초를 넘겨 도착하지 않으면 기존 `frame_gap_sec`에 따라 `UNKNOWN`으로 응답합니다.
- 두 요청 모두 `X-Walkaid-Session` 헤더에 보행 안내 시작 시 생성한 같은 ID(예: `crypto.randomUUID()`)를 넣습니다. 서버는 한 번에 한 카메라만 처리합니다. 다른 스트림은 기존 입력이 끊긴 뒤 시작할 수 있습니다.
- 응답을 받은 뒤 다음 프레임을 보냅니다. 오류 응답과 연결 끊김은 모두 웹앱에서 `UNKNOWN`으로 처리하고, 요청이 끊기거나 1초 넘게 응답이 없으면 이전 안내를 폐기합니다.
- 한 요청은 JPEG 2 MiB 이하입니다. 640×480이나 720p를 권장합니다. 받은 프레임은 메모리에서만 처리합니다.
- 실기기 시험 시 프레임 송신 직전부터 JSON 응답까지 `performance.now()`로 재고, 시작 프레임과 이후 프레임의 지연을 각각 기록합니다. 카메라나 Wi-Fi를 끊은 뒤 안내가 `UNKNOWN`으로 바뀌는 것도 확인합니다.

## 테스트

```bash
pytest          # 단위 테스트
ruff check .    # 문법·스타일
```

PR 마다 GitHub Actions 가 같은 검사를 돌립니다.

## 협업 규칙

브랜치·커밋·PR·리뷰·머지 규칙은 [`CONTRIBUTING.md`](CONTRIBUTING.md), 팀 규칙은 [`docs/team-rules.md`](docs/team-rules.md).
AI 사용 기록은 [`PROMPTS.md`](PROMPTS.md), 윤리적 판단은 [`ETHICS.md`](ETHICS.md).
PR·리뷰·CI 슬랙 알림은 [`docs/slack-notifications.md`](docs/slack-notifications.md).

## 데이터와 개인정보

영상·이미지·모델 가중치는 저장소에 올리지 않습니다(`.gitignore`). 블러 처리된 데이터만 팀 공유 드라이브에 둡니다.
실시간 카메라 프레임은 판단 후 바로 버립니다.

## 라이선스·출처

- OpenCV (Apache-2.0)
- Ultralytics YOLO 를 D1·D2 에서 쓸 예정 (AGPL-3.0) — 도입 시 여기에 추가
