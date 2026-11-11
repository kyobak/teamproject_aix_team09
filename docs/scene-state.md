# SceneState 스키마

> 초안(AI 보조 작성, PROMPTS.md 기록). 팀원 3명이 PR 에서 승인하면 확정합니다(#1).

SceneState 는 **검출기와 판단 모듈 사이의 유일한 약속**입니다. 검출기(D0·D1·D2)는 프레임 한 장마다 SceneState 하나를 만들고, 상태 머신은 SceneState 만 읽습니다. 그래서 검출 방법을 바꿔도 상태 머신과 안내 모듈은 고치지 않습니다.

코드: `walkaid/logic/scene_state.py`

```
camera_source.frames() ──Frame(image, ts)──▶ Detector.detect() ──SceneState──▶ SignalFSM.update() ──State──▶ Announcer
                                                                     └──────────▶ debug_view (#10)
```

## 예시

```json
{
  "ts": 12.4,
  "frame_ok": true,
  "signal": {"present": true, "color": "green", "conf": 0.91, "pos_check": true},
  "paving": {"present": true, "type": "line", "offset": "left", "conf": 0.78}
}
```

## 필드

### 최상위

| 필드 | 타입 | 값 | 뜻 |
|---|---|---|---|
| `ts` | float | 초 | 프레임 시각. 영상 파일이면 영상 안의 시각, 웹캠이면 컴퓨터 시각(`camera_source.py` 가 정함) |
| `frame_ok` | bool | true / false | 이 프레임을 판단에 쓸 수 있는가 |
| `signal` | SignalInfo | 아래 표 | 보행 신호등 |
| `paving` | PavingInfo | 아래 표 | 점자블록 |

### `signal` — 보행 신호등

| 필드 | 타입 | 값 | 뜻 |
|---|---|---|---|
| `present` | bool | true / false | 화면에 보행 신호등이 있는가 |
| `color` | str | `red` `green` `off` `unknown` | 켜진 불의 색 |
| `conf` | float | 0.0 ~ 1.0 | `color` 를 얼마나 확신하는가 |
| `pos_check` | bool | true / false | 켜진 불의 위치가 색과 맞는가 (위 = 빨강, 아래 = 초록) |

`color` 값의 뜻

| 값 | 언제 |
|---|---|
| `red` | 위쪽 불이 빨갛게 켜짐 |
| `green` | 아래쪽 불이 초록으로 켜짐 |
| `off` | 신호등은 보이지만 켜진 불이 없음. 점멸의 꺼진 순간이 여기에 해당 |
| `unknown` | 색을 정할 수 없음. 신호등이 없을 때, 확신이 낮을 때, 색과 위치가 어긋날 때 |

### `paving` — 점자블록

| 필드 | 타입 | 값 | 뜻 |
|---|---|---|---|
| `present` | bool | true / false | 화면에 점자블록이 있는가 |
| `type` | str | `line` `dot` `none` | 선형(방향 안내) / 점형(멈춤·경고) / 없음 |
| `offset` | str | `left` `center` `right` `none` | 점자블록이 화면 중심에서 어느 쪽에 있는가 |
| `conf` | float | 0.0 ~ 1.0 | 판단을 얼마나 확신하는가 |

`offset` 을 나누는 기준(가운데로 볼 폭)은 #14 에서 `config.yaml` 에 정합니다.

## 지켜야 할 규칙

검출기가 지키는 규칙입니다. 상태 머신은 이 규칙을 믿되, 안전을 위해 아래 "상태 머신이 다시 확인하는 것" 을 한 번 더 봅니다.

1. **신호등이 없으면 기본값.** `present=false` 이면 `color="unknown"`, `conf=0.0`, `pos_check=false` 입니다. 점자블록도 같아서 `present=false` 이면 `type="none"`, `offset="none"`, `conf=0.0` 입니다.
2. **확신이 낮으면 `unknown`.** `conf` 가 `config.yaml` 의 `signal.min_conf`(지금 0.8)보다 낮으면 `color="unknown"` 으로 냅니다.
3. **색과 위치가 어긋나면 `unknown`.** 빨강인데 아래쪽 불이거나 초록인데 위쪽 불이면 `pos_check=false`, `color="unknown"` 입니다(#6).
4. **`pos_check` 는 빨강·초록일 때만 true.** `off`·`unknown` 이면 비교할 켜진 불이 없으므로 항상 false 입니다.
5. **신호등이 여러 개면 하나만.** 횡단보도 건너편에서 이쪽을 향한 보행 신호등 중 가장 큰 것 하나만 씁니다. 차량 신호등은 보행 신호로 쓰지 않습니다.
6. **판단할 수 없는 프레임은 `frame_ok=false`.** 이미지가 비었거나 전부 검은 경우처럼 볼 수 없는 프레임입니다. 이때 `signal`·`paving` 은 기본값입니다.
7. **`ts` 는 늘어나기만 합니다.** 같은 입력에서 뒤 프레임의 `ts` 가 앞 프레임보다 작으면 안 됩니다.

## 상태 머신이 다시 확인하는 것 (#7)

검출이 틀려도 "함부로 건너라고 하지 않는" 성질을 지키기 위해서입니다.

- `frame_ok=false` 이거나 앞 프레임과 `ts` 차이가 `fsm.frame_gap_sec`(1초)보다 크면 UNKNOWN 입니다. 끊김은 SceneState 에 따로 적지 않고 `ts` 로 계산합니다.
- `red`·`green` 은 `pos_check=true` 일 때만 관찰로 셉니다.
- `off` 는 `present=true` 일 때만 셉니다. 초록과 번갈아 나오면 점멸(BLINK)입니다.
- `unknown` 은 어떤 상태로도 바꾸지 않습니다.
- `unknown` 은 이어지던 연속 횟수를 끊습니다. 그래서 초록 사이에 `unknown` 이 끼면 CROSS 까지 다시 3프레임을 셉니다.
- CROSS 는 WAIT(빨강 3프레임)를 본 뒤 `fsm.arm_sec`(2초) 안에 초록이 시작됐을 때만 냅니다. 도착했을 때 이미 초록이면 남은 시간을 모르므로 CROSS 를 내지 않습니다.
- CROSS 중 초록이 `fsm.cross_hold_sec`(1초) 넘게 안 보이면 UNKNOWN 입니다. 빨간불이 `unknown` 으로만 나와도 CROSS 가 남아 있지 않게 하기 위해서입니다.

## 누가 무엇을 쓰고 읽나

| 모듈 | 쓰는 것 | 읽는 것 |
|---|---|---|
| `walkaid/logic/detector/` (D0·D1·D2) | SceneState 전체 | 이미지, `ts`, `config.yaml` |
| `walkaid/logic/signal_color.py` (#6) | `signal.color` `conf` `pos_check` | 신호등 박스 이미지 |
| `walkaid/logic/paving_offset.py` (#14) | `paving` 전체 | 점자블록 마스크 |
| `walkaid/logic/signal_fsm.py` (#7) | 없음 (State 를 냄) | `ts` `frame_ok` `signal` |
| `walkaid/present/debug_view.py` (#10) | 없음 | SceneState 전체 |
| `walkaid/present/announcer.py` (#8) | 없음 | SceneState 를 읽지 않고 State 만 받음 |

## 저장하지 않는 것

SceneState 에는 이미지가 들어가지 않습니다. 실행 기록(`logs/decisions.csv`)에도 상태와 시각만 남기고 프레임은 판단 후 바로 버립니다(`README.md` 데이터와 개인정보).

## 바꾸는 방법

모든 모듈이 SceneState 에 기대고 있으므로, 필드를 더하거나 뜻을 바꿀 때는 이 문서, `scene_state.py`, 관련 테스트를 **한 PR 에서 함께** 고치고 팀원 모두에게 리뷰를 요청합니다.
