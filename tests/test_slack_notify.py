"""슬랙 알림 테스트 — 보낼 것만 보내고, 틀을 지키고, 제목으로 전체 멘션을 걸 수 없다."""

import json
from pathlib import Path

import pytest

from tools import slack_notify
from tools.slack_notify import build_message


def review_pr(**overrides) -> dict:
    # pull_request_review 이벤트의 PR 에는 additions·merged 같은 값이 없습니다. 실제 모양과 같게 둡니다.
    base = {
        "html_url": "https://github.com/o/r/pull/7",
        "number": 7,
        "title": "feat(#7): add BLINK",
        "user": {"login": "alice"},
        "labels": [],
        "requested_reviewers": [],
        "requested_teams": [],
    }
    return base | overrides


def pr(**overrides) -> dict:
    base = review_pr() | {
        "draft": False,
        "merged": False,
        "head": {"ref": "feat/7-blink"},
        "base": {"ref": "main"},
        "additions": 120,
        "deletions": 4,
        "changed_files": 3,
    }
    return base | overrides


def ci_run(**overrides) -> dict:
    base = {
        "conclusion": "failure",
        "event": "push",
        "head_branch": "main",
        "head_sha": "abcdef1234",
        "html_url": "https://github.com/o/r/actions/runs/1",
        "head_commit": {"message": "feat(#7): add BLINK\n\nbody"},
        "actor": {"login": "alice"},
    }
    return {"workflow_run": base | overrides}


def issue(**overrides) -> dict:
    base = {
        "html_url": "https://github.com/o/r/issues/1",
        "number": 1,
        "title": "t",
        "user": {"login": "a"},
        "author_association": "COLLABORATOR",
        "assignees": [],
        "labels": [],
    }
    return base | overrides


def review(state: str, body: str | None = None) -> dict:
    return {
        "action": "submitted",
        "pull_request": review_pr(),
        "review": {"state": state, "body": body, "user": {"login": "bob"}},
    }


def test_title_cannot_mention_channel():
    text = build_message("pull_request", {"action": "opened", "pull_request": pr(title="<!channel> a&b")})
    assert "<!channel>" not in text
    assert "&lt;!channel&gt; a&amp;b" in text


@pytest.mark.parametrize(
    ("event", "payload", "title"),
    [
        ("pull_request", {"action": "opened", "pull_request": pr()}, "📬 새 PR"),
        ("pull_request", {"action": "ready_for_review", "pull_request": pr()}, "📬 새 PR"),
        (
            "pull_request",
            {"action": "review_requested", "pull_request": pr(), "requested_reviewer": {"login": "bob"}},
            "👀 리뷰어 지정",
        ),
        (
            "pull_request",
            {"action": "closed", "pull_request": pr(merged=True), "sender": {"login": "alice"}},
            "✅ 머지 완료",
        ),
        ("pull_request_review", review("approved"), "👍 승인"),
        ("pull_request_review", review("changes_requested"), "✋ 수정 요청"),
        ("issues", {"action": "opened", "issue": issue()}, "📝 새 이슈"),
        ("workflow_run", ci_run(), "🚨 main CI 실패"),
    ],
)
def test_every_message_follows_the_template(event, payload, title):
    lines = build_message(event, payload).splitlines()
    assert lines[0] == f"*{title}*"
    assert lines[1].startswith("<https://github.com/")
    assert all(line.startswith("• ") for line in lines[2:-1])
    assert len(lines) > 3
    assert lines[-1].startswith("👉 ")


def test_new_pr_shows_branch_size_and_reviewers():
    waiting = pr(requested_reviewers=[{"login": "bob"}], requested_teams=[{"name": "vision"}])
    text = build_message("pull_request", {"action": "opened", "pull_request": waiting})
    assert "• 브랜치: feat/7-blink → main" in text
    assert "• 변경: +120 / -4 (파일 3개)" in text
    assert "• 리뷰어: bob, vision" in text
    assert "24시간 안에 리뷰" in text


def test_new_pr_without_reviewer_asks_author_to_assign():
    text = build_message("pull_request", {"action": "opened", "pull_request": pr()})
    assert "• 리뷰어: 없음" in text
    assert "작성자: 리뷰어를 지정" in text


def test_draft_pr_is_not_announced():
    assert build_message("pull_request", {"action": "opened", "pull_request": pr(draft=True)}) is None


def test_safety_label_shows_merge_rule():
    labeled = pr(labels=[{"name": "safety"}])
    assert "Approve 2명" in build_message("pull_request", {"action": "opened", "pull_request": labeled})


def test_review_request_names_reviewer():
    payload = {"action": "review_requested", "pull_request": pr(), "requested_reviewer": {"login": "bob"}}
    assert "• 리뷰어: bob" in build_message("pull_request", payload)


def test_review_request_for_team_has_no_reviewer_field():
    payload = {"action": "review_requested", "pull_request": pr(), "requested_team": {"name": "vision"}}
    assert "• 리뷰어: vision" in build_message("pull_request", payload)


def test_only_merged_close_is_announced():
    assert build_message("pull_request", {"action": "closed", "pull_request": pr()}) is None


def test_merge_shows_who_merged():
    payload = {"action": "closed", "pull_request": pr(merged=True), "sender": {"login": "carol"}}
    assert "• 머지한 사람: carol" in build_message("pull_request", payload)


def test_plain_comment_review_is_not_announced():
    assert build_message("pull_request_review", review("commented")) is None


def test_changes_requested_shows_first_line_of_reason():
    text = build_message("pull_request_review", review("changes_requested", "[must] <red> 처리\n자세한 내용"))
    assert "• 내용: [must] &lt;red&gt; 처리" in text
    assert "자세한 내용" not in text


@pytest.mark.parametrize("body", [None, "", "  \n "])
def test_changes_requested_without_reason_omits_field(body):
    assert "내용" not in build_message("pull_request_review", review("changes_requested", body))


@pytest.mark.parametrize(("association", "announced"), [("COLLABORATOR", True), ("NONE", False)])
def test_only_team_issues_are_announced(association, announced):
    payload = {"action": "opened", "issue": issue(author_association=association)}
    assert (build_message("issues", payload) is not None) == announced


def test_issue_without_owner_asks_to_assign():
    assert "담당자를 지정" in build_message("issues", {"action": "opened", "issue": issue()})
    owned = issue(assignees=[{"login": "bob"}])
    assert "• 담당: bob" in build_message("issues", {"action": "opened", "issue": owned})


def test_ci_failure_only_on_main_push():
    text = build_message("workflow_run", ci_run())
    assert "abcdef1" in text
    assert "• 커밋: feat(#7): add BLINK" in text
    assert "body" not in text
    assert build_message("workflow_run", ci_run(conclusion="success")) is None
    assert build_message("workflow_run", ci_run(event="pull_request")) is None
    assert build_message("workflow_run", ci_run(head_branch="feat/7-x")) is None


def test_missing_secret_skips_without_failing(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    assert slack_notify.main() == 0


def test_main_posts_message_to_webhook(monkeypatch, tmp_path: Path):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"action": "opened", "pull_request": pr()}), encoding="utf-8")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.example/x")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    sent = []
    monkeypatch.setattr(slack_notify, "send", lambda url, text: sent.append((url, text)))
    assert slack_notify.main() == 0
    assert sent[0][0] == "https://hooks.example/x"
    assert "#7" in sent[0][1]
