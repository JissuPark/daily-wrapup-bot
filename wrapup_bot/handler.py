"""[승인] 클릭 1건 판단 — Slack 과 무관한 순수 로직."""
from collections import namedtuple
from datetime import datetime

from wrapup_bot import cardfmt
from wrapup_bot.jira import TRACK, JiraError

Result = namedtuple("Result", "text retry")


def handle_approval(value: dict, blocks: list, user_id: str, now: datetime,
                    allowed_user_id: str, jira, dry_run: bool) -> Result:
    if user_id != allowed_user_id:
        return Result("🚫 권한 없음", True)
    if cardfmt.is_expired(value["expires_at"], now):
        return Result("⌛ 만료 — 볼트에 이월됨", False)

    kind, key, item_id = value["kind"], value["key"], value["id"]
    if kind == "comment":
        body = cardfmt.extract_body(blocks, item_id)
        if body is None:
            return Result("❌ 원문 없음", False)
        if TRACK % item_id not in body:  # 추적 줄이 없으면 멱등 확인이 무력해진다
            return Result("❌ 추적 줄 없음", False)
        item = {"kind": kind, "key": key, "body": body}
    elif kind == "transition":
        item = {"kind": kind, "key": key, "to_status": value.get("to_status") or ""}
    else:
        return Result("❌ 알 수 없는 항목", False)
    if cardfmt.item_hash(item) != value.get("sha256"):
        return Result("❌ 원문 불일치", False)

    try:
        if kind == "comment":
            done = jira.find_tracked_comment(key, item_id)
            if done:
                return Result("⏭ 이미 게시 #%s" % done, False)
        else:
            cur = jira.current_status(key)
            if cur.strip() == item["to_status"].strip():
                return Result("⏭ 이미 %s" % cur, False)
        if dry_run:
            return Result("🧪 DRY-RUN: %s %s 게시 예정" % (key, kind), True)
        if kind == "comment":
            return Result("✅ 게시 #%s" % jira.add_comment(key, item["body"]), False)
        jira.transition_to(key, item["to_status"])
        return Result("✅ %s(으)로 전환" % item["to_status"], False)
    except JiraError as e:
        return Result("❌ %s — 다시 누를 수 있음" % e, True)
