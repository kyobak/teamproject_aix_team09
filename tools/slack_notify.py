"""GitHub 이벤트를 슬랙 메시지로 보냅니다. .github/workflows/slack-notify.yml 에서 실행합니다.

새 라이브러리 추가는 사람이 결정하는 규칙이라(CONTRIBUTING 6절) 표준 라이브러리만 씁니다.
메시지 틀은 docs/slack-notifications.md 에 있습니다. 문구를 바꾸면 문서도 같이 고칩니다.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

# 저장소가 공개라 외부인도 이슈를 열 수 있습니다. 팀원이 연 이슈만 알려서 채널 도배를 막습니다.
TEAM_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}

SUMMARY_LIMIT = 100


def esc(text: str) -> str:
    # 슬랙은 <!channel> 을 전체 멘션으로 읽습니다. 제목에 이런 글자가 있어도 글자 그대로 보이게 바꿉니다.
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def link(item: dict) -> str:
    return f"<{item['html_url']}|#{item['number']} {esc(item['title'])}>"


def render(title: str, target: str, fields: list[tuple[str, str]], next_step: str) -> str:
    # 어떤 알림이든 "무슨 일 → 대상 → 정보 → 다음 행동" 순서로 보여서, 맨 아래 줄만 봐도 할 일을 알 수 있게 합니다.
    lines = [f"*{title}*", target]
    lines += [f"• {name}: {value}" for name, value in fields]
    lines.append(f"👉 {next_step}")
    return "\n".join(lines)


def names(values: list[str]) -> str:
    return ", ".join(esc(value) for value in values) or "없음"


def summary(text: str) -> str:
    # 긴 글은 GitHub 에서 읽으면 되므로 첫 줄만 보여 줍니다. 잘린 &amp; 가 깨지지 않게 자른 뒤에 바꿉니다.
    return esc(text.strip().splitlines()[0][:SUMMARY_LIMIT]) if text.strip() else ""


def reviewers(pr: dict) -> list[str]:
    people = [person["login"] for person in pr["requested_reviewers"]]
    return people + [team["name"] for team in pr["requested_teams"]]


def label_names(item: dict) -> list[str]:
    return [label["name"] for label in item["labels"]]


def safety_fields(pr: dict) -> list[tuple[str, str]]:
    # 안전 파일은 머지 조건이 다르므로(CONTRIBUTING 5절) 리뷰하는 사람이 놓치지 않게 표시합니다.
    if "safety" in label_names(pr):
        return [("⚠️ 안전 파일", "Approve 2명 + 테스트 클립 CROSS 0회 결과 첨부")]
    return []


def branch(pr: dict) -> str:
    return f"{esc(pr['head']['ref'])} → {esc(pr['base']['ref'])}"


def changes(pr: dict) -> str:
    # 리뷰 시간을 가늠하는 값입니다. additions 등은 pull_request 이벤트에만 있어서 리뷰 알림에는 쓰지 않습니다.
    return f"+{pr['additions']} / -{pr['deletions']} (파일 {pr['changed_files']}개)"


def pull_request_message(payload: dict) -> str | None:
    action, pr = payload["action"], payload["pull_request"]
    author = esc(pr["user"]["login"])
    if action in ("opened", "ready_for_review"):
        # Draft 는 방향을 묻는 단계라(CONTRIBUTING 3절) 리뷰 준비가 끝났을 때만 알립니다.
        if pr["draft"]:
            return None
        waiting = reviewers(pr)
        fields = [
            ("작성자", author),
            ("브랜치", branch(pr)),
            ("변경", changes(pr)),
            ("리뷰어", names(waiting)),
            ("라벨", names(label_names(pr))),
        ]
        next_step = "리뷰어: 24시간 안에 리뷰해 주세요" if waiting else "작성자: 리뷰어를 지정해 주세요"
        return render("📬 새 PR", link(pr), fields + safety_fields(pr), next_step)
    if action == "review_requested":
        # 팀 단위 리뷰 요청에는 requested_reviewer 가 없어서 requested_team 도 봅니다.
        reviewer = payload.get("requested_reviewer") or {}
        name = esc(reviewer.get("login") or payload.get("requested_team", {}).get("name", "?"))
        fields = [("리뷰어", name), ("작성자", author), ("변경", changes(pr))]
        next_step = f"{name}: 24시간 안에 리뷰해 주세요 (마감 24시간 이내 PR 은 2시간)"
        return render("👀 리뷰어 지정", link(pr), fields + safety_fields(pr), next_step)
    if action == "closed" and pr["merged"]:
        fields = [
            ("작성자", author),
            ("머지한 사람", esc(payload["sender"]["login"])),
            ("브랜치", branch(pr)),
            ("변경", changes(pr)),
        ]
        return render("✅ 머지 완료", link(pr), fields, "모두: 새 작업 전에 main 을 최신으로 받아 주세요 (git pull)")
    return None


def review_message(payload: dict) -> str | None:
    if payload["action"] != "submitted":
        return None
    review, pr = payload["review"], payload["pull_request"]
    fields = [("리뷰어", esc(review["user"]["login"])), ("작성자", esc(pr["user"]["login"]))]
    # 일반 코멘트까지 보내면 알림이 너무 많아서, 머지 여부를 바꾸는 두 결과만 보냅니다.
    if review["state"] == "approved":
        fields += [("남은 리뷰어", names(reviewers(pr)))] + safety_fields(pr)
        return render("👍 승인", link(pr), fields, "작성자: 머지 조건을 확인하고 Squash and merge 해 주세요")
    if review["state"] == "changes_requested":
        if reason := summary(review["body"] or ""):
            fields.append(("내용", reason))
        return render("✋ 수정 요청", link(pr), fields, "작성자: [must] 코멘트를 해결하고 리뷰를 다시 요청해 주세요")
    return None


def issue_message(payload: dict) -> str | None:
    issue = payload["issue"]
    if payload["action"] != "opened" or issue["author_association"] not in TEAM_ASSOCIATIONS:
        return None
    owners = [person["login"] for person in issue["assignees"]]
    fields = [("작성자", esc(issue["user"]["login"])), ("담당", names(owners)), ("라벨", names(label_names(issue)))]
    next_step = "담당자: 완료 조건을 확인해 주세요" if owners else "작성자: 담당자를 지정해 주세요"
    return render("📝 새 이슈", link(issue), fields, next_step)


def ci_message(payload: dict) -> str | None:
    run = payload["workflow_run"]
    # PR 의 CI 실패는 작성자만 고치면 되지만, main 이 깨지면 팀 전체가 멈추므로 main 만 알립니다.
    # 포크 브랜치 이름도 main 일 수 있어서 push 이벤트인지 함께 확인합니다.
    if run["conclusion"] != "failure" or run["event"] != "push" or run["head_branch"] != "main":
        return None
    target = f"<{run['html_url']}|커밋 {run['head_sha'][:7]} 실행 기록>"
    fields = [("커밋", summary(run["head_commit"]["message"])), ("올린 사람", esc(run["actor"]["login"]))]
    next_step = "머지한 사람: 먼저 GitHub Revert, 그다음 fix/ 브랜치로 다시 PR 하세요"
    return render("🚨 main CI 실패", target, fields, next_step)


BUILDERS = {
    "pull_request": pull_request_message,
    "pull_request_review": review_message,
    "issues": issue_message,
    "workflow_run": ci_message,
}


def build_message(event_name: str, payload: dict) -> str | None:
    builder = BUILDERS.get(event_name)
    return builder(payload) if builder else None


def send(webhook_url: str, text: str) -> None:
    body = json.dumps({"text": text, "unfurl_links": False}).encode()
    request = urllib.request.Request(webhook_url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10):
        pass


def main() -> int:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    # 포크 PR 에는 시크릿이 전달되지 않습니다. 알림 때문에 PR 검사가 빨갛게 되지 않도록 그냥 건너뜁니다.
    if not webhook_url:
        print("SLACK_WEBHOOK_URL 이 없어 알림을 건너뜁니다")
        return 0
    payload = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    text = build_message(os.environ["GITHUB_EVENT_NAME"], payload)
    if text is None:
        print("알림 대상이 아닌 이벤트입니다")
        return 0
    send(webhook_url, text)
    print("슬랙 알림을 보냈습니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
