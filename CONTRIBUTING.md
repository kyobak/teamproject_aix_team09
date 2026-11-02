# 협업 규칙 / Contributing

> 팀 개발 계획 문서의 규칙을 저장소용으로 옮긴 것입니다. 바꾸려면 PR 로 제안합니다.

## 1. 브랜치 규칙 (GitHub Flow)

- `main` 하나 + 이슈마다 짧게 사는 작업 브랜치. **main 에 직접 push 금지**(GitHub 설정으로 막혀 있음).
- 이름: `종류/이슈번호-짧은-설명` (영어 소문자, 하이픈). 이슈가 없는 문서 작업(활동지, 협업 규칙)만 번호 없이 `docs/짧은-설명`.
- 이슈와 PR 은 번호를 함께 씁니다. 브랜치를 만들기 전에 `gh issue view 번호` 로 제목을 확인합니다.
- **작업 하나 = 브랜치 하나.** 다른 작업으로 옮기기 전에 지금 브랜치에 커밋합니다. 중간 커밋(`wip(#7): checkpoint`)도 괜찮습니다 — Squash merge 라 main 에는 PR 하나당 커밋 하나만 남습니다. 여러 작업을 한 폴더에 섞어 두지 않습니다.
- 다른 사람의 PR 이 끝나기를 기다리는 이슈도 그 브랜치 위에 쌓지 말고 main 에서 따서 작업합니다(예: #7 은 #6 을 기다리지만 SceneState 로만 대화하므로 따로 개발 가능).

| 종류 | 언제 | 예시 |
|---|---|---|
| `feat` | 기능 추가 | `feat/7-signal-fsm` |
| `fix` | 버그 수정 | `fix/21-red-mask-wrap` |
| `test` | 테스트만 | `test/6-color-cases` |
| `docs` | 문서·활동지 | `docs/week-09` |
| `data` | 데이터 도구·라벨 목록 | `data/4-blur-extract` |
| `exp` | 실험(머지 안 해도 됨) | `exp/hsv-tuning` |

```bash
git switch main && git pull
git switch -c feat/7-signal-fsm
# ... 작업, 커밋 ...
git pull --rebase origin main      # PR 을 열기 전에만
git push -u origin feat/7-signal-fsm
```

PR 을 연 뒤에 main 의 새 내용을 받을 때는 rebase 하지 않습니다(force push 가 필요해짐). PR 화면의 **Update branch** 버튼이나 `git merge origin/main` 을 씁니다.

## 2. 커밋 메시지

`종류(#이슈): 무엇을 했는지` — 제목은 영어 명령형, 본문은 필요하면 한국어로 "왜".

```
feat(#7): add BLINK state to signal FSM
fix(#21): handle red hue wraparound at 170-179
docs(#1): define SceneState schema
```

금지: `update`, `fix`, `wip` 같은 내용 없는 메시지 / 영상·이미지·`.pt`·`.env` 커밋 / 남의 브랜치 force push.

## 3. PR 규칙

- PR 1개 = 이슈 1개, 코드 변경 **400줄 이하**(테스트·문서 제외).
- 제목은 커밋 형식과 같게(Squash merge 때 main 커밋 제목이 됩니다). 본문은 템플릿의 모든 칸을 채우고 `Closes #번호`. 이슈가 없는 문서 PR 은 `Closes` 칸에 "없음"과 이유를 씁니다.
- **본인 말로 3줄 설명** 필수 — 이해하지 못한 코드는 올리지 않습니다.
- 비전·모델 PR 은 같은 테스트셋의 전/후 숫자를, 화면·음성 PR 은 스크린샷이나 짧은 영상을 붙입니다.
- 방향을 먼저 묻고 싶으면 Draft PR. 안전 파일을 바꾸는 큰 작업(예: #7)은 Draft 를 일찍 열어 방향부터 받습니다.
- 라벨: 영역 1개(`vision` `logic` `data` `output` `ml` `test` `docs`) + 필요 시 `safety` / `blocked`.

## 4. 리뷰 규칙

- 리뷰 요청은 **24시간 안에**(마감 24시간 이내 PR 은 2시간). 주 리뷰 담당이 못 보면 누구나 리뷰해도 됩니다.
- 보는 순서: 완료 조건 → 실패 경로 → 계층 경계(SceneState 로만 대화하는가) → 설명 가능성 → 스타일.
- 코멘트 말머리:

| 말머리 | 뜻 | 머지 전 해결? |
|---|---|---|
| `[must]` | 버그, 완료 조건 미충족, 안전 문제 | 예 |
| `[ask]` | 이해가 안 되니 설명해 달라 | 답변은 예 |
| `[suggest]` | 더 나은 방법 제안 | 작성자 판단 |
| `[nit]` | 사소한 것 | 아니오 |

| 영역 | 주 담당 | 주 리뷰 담당 |
|---|---|---|
| 로직·통합 (`walkaid/logic/signal_fsm.py`, `walkaid/main.py`, `docs/`) | 박재원 | 박지성 |
| 비전·모델 (`walkaid/logic/detector/`, `signal_color.py`, `training/`) | 박지성 | 박재원 |
| 데이터 (`walkaid/io/`, `tools/`, `paving_offset.py`) | 강태혁 | 전시준 |
| 출력·시연·문서 (`walkaid/present/`, README) | 전시준 | 강태혁 |

## 5. 머지 규칙

**모든 PR** — Approve 1명, CI 통과, 대화 Resolve, Squash 만, 머지 후 브랜치 삭제는 GitHub 설정으로 강제됩니다(관리자 포함). Slack 알림(`notify`)은 필수 검사가 아니라서 알림이 실패해도 머지는 막히지 않습니다.
- [ ] 작성자 외 1명 이상 Approve
- [ ] CI(ruff + pytest) 통과
- [ ] `[must]` 코멘트 모두 해결, 대화 모두 Resolve
- [ ] main 최신 상태와 충돌 없음
- [ ] 템플릿 빈 칸 없음, `Closes #번호` 있음

**안전 파일**(`walkaid/logic/signal_fsm.py`, `walkaid/logic/signal_color.py`, `config.yaml`) — `safety` 라벨
- [ ] Approve **2명**
- [ ] 테스트 클립 전체에서 "빨간불·점멸 중 CROSS 안내 0회" 결과 첨부
- [ ] 바꾼 임계값의 전/후 값과 이유

**방식**
- **Squash and merge 만** 사용. main 커밋 1개 = PR 1개 = 이슈 1개.
- 머지는 **PR 작성자가** 합니다. 머지 후 브랜치는 자동 삭제.
- 머지 후 main 이 깨지면 → 먼저 GitHub Revert, 그다음 `fix/` 브랜치로 다시 PR.
- **기능 동결**: 11/27(13주차 금)부터 데모데이까지 `fix`·`docs`·`test` 만. 데모 버전은 `v1.0-demo` 태그.

## 6. AI 에이전트 사용

- 에이전트에게는 이슈 하나 + 고쳐도 되는 파일 목록 + 실패하는 테스트를 줍니다.
- 다른 계층 파일 수정, 안전 임계값 변경, 새 라이브러리 추가는 사람이 결정합니다.
- AI 결과물이 산출물에 들어가면 `PROMPTS.md` 끝에 `### [#이슈] 이름 · 날짜` 로 추가합니다. 동시에 열린 PR 끼리는 이 파일에서 충돌이 나기 쉽습니다. 나중에 머지하는 사람이 **Update branch** 후 두 기록을 모두 남기는 쪽으로 풀면 됩니다.
- 실명·학번·연락처·블러 안 한 사진은 에이전트에 넣지 않습니다.

## 7. 데이터

| 무엇 | 어디에 |
|---|---|
| 블러 처리된 영상·프레임 | 팀 공유 드라이브 `data/frames/` |
| YOLO 라벨, `clips.csv`, 분할 목록 | 저장소 `data/labels/`, `data/splits/` |
| 모델 가중치 | GitHub Release 또는 드라이브 `models/` |
| 원본 영상 | 블러 처리 후 삭제 |

학습·검증·테스트는 **장소 단위로** 나누고, 학습 시 색상 증강은 끕니다(`hsv_h=0`).
