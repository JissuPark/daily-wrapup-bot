import json
from datetime import datetime

from wrapup_bot import cardfmt
from wrapup_bot.handler import handle_approval
from wrapup_bot.jira import JiraError

EXP = "2026-11-07T11:00:00+09:00"
NOW = datetime.fromisoformat("2026-11-06T12:00:00+09:00")
LATE = datetime.fromisoformat("2026-11-07T11:00:01+09:00")
ME = "U_ME"
BODY = "*진행*\n----\n_wrapup 승인 게시 · c1_"


class FakeJira:
    def __init__(self, tracked=None, status="작업요청", err=None):
        self.tracked, self.status, self.err = tracked, status, err
        self.added, self.moved = [], []

    def find_tracked_comment(self, key, item_id):
        return self.tracked

    def add_comment(self, key, body):
        if self.err:
            raise self.err
        self.added.append((key, body))
        return "777"

    def current_status(self, key):
        return self.status

    def transition_to(self, key, to_status):
        if self.err:
            raise self.err
        self.moved.append((key, to_status))


def card(items):
    q = {"run_id": "r", "expires_at": EXP, "summary": "", "items": items, "links": []}
    blocks = [b for m in cardfmt.build_messages(q) for b in m["blocks"]]
    vals = {b["block_id"][:-4]: json.loads(b["elements"][0]["value"]) for b in blocks if b.get("block_id", "").endswith(":act")}
    return blocks, vals


C = {"id": "c1", "kind": "comment", "key": "PROJ-1", "title": "t", "body": BODY}
T = {"id": "t1", "kind": "transition", "key": "PROJ-1", "title": "t", "to_status": "진행 중"}


def run(item, jira, user=ME, now=NOW, dry=False, blocks=None):
    b, vals = card([item])
    return handle_approval(vals[item["id"]], blocks if blocks is not None else b, user, now, ME, jira, dry)


def test_not_allowed_user():
    j = FakeJira()
    r = run(C, j, user="U_OTHER")
    assert r.text == "🚫 권한 없음" and r.retry and not j.added


def test_expired():
    r = run(C, FakeJira(), now=LATE)
    assert r.text == "⌛ 만료 — 볼트에 이월됨" and not r.retry


def test_missing_body_rejected():
    other, _ = card([dict(C, id="zz")])
    j = FakeJira()
    r = run(C, j, blocks=other)
    assert r.text == "❌ 원문 없음" and not j.added


def test_hash_mismatch():
    b, vals = card([C])
    for x in b:
        if x.get("block_id") == "c1:p1":
            x["text"]["text"] = x["text"]["text"].replace("진행", "진헹")
    j = FakeJira()
    r = handle_approval(vals["c1"], b, ME, NOW, ME, j, False)
    assert r.text == "❌ 원문 불일치" and not j.added


def test_comment_already_posted():
    j = FakeJira(tracked="555")
    r = run(C, j)
    assert r.text == "⏭ 이미 게시 #555" and not j.added


def test_transition_already_done():
    j = FakeJira(status="진행 중")
    assert run(T, j).text == "⏭ 이미 진행 중" and not j.moved


def test_dry_run_no_write():
    j = FakeJira()
    r = run(C, j, dry=True)
    assert r.text == "🧪 DRY-RUN: PROJ-1 comment 게시 예정" and r.retry and not j.added


def test_comment_posted():
    j = FakeJira()
    r = run(C, j)
    assert r.text == "✅ 게시 #777" and not r.retry
    assert j.added == [("PROJ-1", cardfmt.normalize(BODY))]


def test_transition_done():
    j = FakeJira()
    assert run(T, j).text == "✅ 진행 중(으)로 전환" and j.moved == [("PROJ-1", "진행 중")]


def test_transition_hash_tamper():
    _, vals = card([T])
    v = dict(vals["t1"], to_status="반려")
    j = FakeJira()
    assert handle_approval(v, [], ME, NOW, ME, j, False).text == "❌ 원문 불일치" and not j.moved


def test_jira_error_retryable():
    r = run(C, FakeJira(err=JiraError("HTTP 500", 500)))
    assert r.text == "❌ HTTP 500 — 다시 누를 수 있음" and r.retry


def test_missing_tracking_line_refused():
    j = FakeJira()
    r = run(dict(C, body="*진행* 추적 줄 없음"), j)
    assert r.text == "❌ 추적 줄 없음" and not j.added
