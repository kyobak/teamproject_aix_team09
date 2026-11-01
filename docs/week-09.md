# 9주차 활동지 / Week 9 Worksheet

**개발 착수 / Starting development**

> 팀 초안(AI 보조 작성, PROMPTS.md 기록). 검토 후 수정하세요.

- 작성일 / Date: 2026-11-01
- 참여자 / Present: 박재원, 박지성, 강태혁, 전시준

---

## ① 착수 점검표 / Start checklist

수업 시작 후 10분 안에 확인합니다. 체크되지 않은 항목이 있으면 그것부터 해결하고 개발을 시작합니다.
*Check within the first 10 minutes. Fix any unchecked item before you start coding.*

- [x] 초기 파일이 저장소에 올라와 있다 / Initial files are in the repository
- [x] 7주차 이슈가 GitHub에 등록되어 있고 담당자가 지정되어 있다 / Week 7 issues are on GitHub with owners — 16개 모두 등록, 담당자 지정 완료 (11/1)
- [ ] 팀원 모두 같은 환경에서 실행된다 / Everyone can run it in the same environment — 각자 `python tools/check_env.py` 를 실행해 마지막 줄이 OK 인지 확인 필요
- [x] 브랜치 규칙을 정했다 / Branch rule agreed — GitHub Flow: `main` + 작업 브랜치 `종류/이슈번호-짧은-설명`, `main` 직접 push 금지 (`CONTRIBUTING.md` 1절)

---

## ② 개발 일정 / Development schedule

5주차 **작업 순서**와 7주차 **이슈·마일스톤**을 바탕으로 이슈를 주차별로 배치합니다.
*Place your issues week by week, based on the Week 5 work order and Week 7 issues and milestones.*

- 11주차에 MVP가 동작해야 합니다. / Fill backwards from the deadlines.
- 선행 이슈가 끝나기 전에 뒤 이슈를 넣지 않습니다. / Never schedule an issue before the ones it depends on.
- 한 사람에게 몰리지 않았는지 확인합니다. / Check that no one is overloaded.

| 주차 Week | 수업 일정 Class | 끝낼 이슈 # Issues to close | 담당 Owner |
|---|---|---|---|
| 9주차 | 개발 착수 | #1, #2, #3 | 박재원(#1), 강태혁(#2), 전시준(#3) |
| 10주차 | 막힘 진단 · 데모 시나리오 초안 | #4, #5, #6, #7, #8 | 강태혁(#4), 박지성(#5, #6), 박재원(#7), 전시준(#8) |
| 11주차 | **MVP 완료 · 중간 데모** | #9, #10 | 박재원(#9), 전시준(#10) |
| 12주차 | 핵심 경로 테스트 | #11, #12, #14 | 전원(#11), 강태혁(#12, #14) |
| 13주차 | **배포 · 실행 패키지** | #13, #15, #16 | 박지성(#13), 박재원(#15), 전시준(#16) |

- **마감 기준**: GitHub 마일스톤 마감은 MVP 11/10(11주차), 실행 패키지 11/24(13주차)입니다. 팀 내부 마감은 하루 전입니다.
- **같은 주 안의 순서**: 10주차는 #6 → #7, 12주차는 #11 → #14, 13주차는 #13 → #15 순서로 끝냅니다.
- **#7 을 10주차로 당긴 이유**: #9 가 #7 을 기다리는데, MVP 마감이 11주차 초반이라 11주차에 둘 다 끝내기 어렵습니다.
- **#11 라벨링**: 12주차에 끝내되 작업은 #4 가 끝나는 대로 병렬로 시작합니다.
- **담당 분포**: 7주차 이슈표 그대로입니다. 박재원 4개, 강태혁 4개, 전시준 4개, 박지성 3개, #11 은 전원.

> 일정이 맞지 않으면 기능을 줄입니다. 뺀 기능은 5주차 Won't 목록에 옮깁니다.
> *If it doesn't fit, cut scope and move the feature to your Week 5 Won't list.*

---

## ③ 이번 주 목표 이슈 / This week's issues

| # | 제목 Title | 담당 Owner | 완료 Done |
|---|---|---|---|
| #1 | Define SceneState schema & label classes | 박재원 | [ ] |
| #2 | Camera/video source abstraction | 강태혁 | [ ] |
| #3 | Capture protocol & field recording | 전시준 | [ ] |

---

## ④ 오늘 진행한 것 / Progress today

- 초기 파일 커밋(`21c96ed`, 10/28): `walkaid/` 3계층 뼈대, 고정 버전 환경과 `tools/check_env.py`, CI, PR 템플릿, CODEOWNERS, `CONTRIBUTING.md`
- GitHub 이슈 16개 등록, 마일스톤 2개(MVP 완료, 실행 패키지) 연결
- 이슈 의존 관계에 맞춰 주차별 일정 배치
- 슬랙 알림 코드 작성(로컬 테스트 통과, 웹훅 등록과 PR 은 남음)
- 11/1 기준 PR 0건, 이슈 16개 모두 Open

- [x] 이번 활동에서 AI를 사용했다면 `PROMPTS.md`에 기록했습니다 / Logged any AI use in `PROMPTS.md`

---

> 수업 종료 시 커밋하세요 / Commit this at the end of class
> `git add docs/week-09.md && git commit -m "docs: 9주차 활동지 작성"`
