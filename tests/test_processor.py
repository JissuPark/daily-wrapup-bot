import json
import threading
import time
from datetime import datetime

from wrapup_bot import cardfmt
from wrapup_bot.processor import Processor

EXP = "2026-11-07T11:00:00+09:00"
NOW = datetime.fromisoformat("2026-11-06T12:00:00+09:00")
ME = "U_ME"


def item(i):
    return {"id": i, "kind": "comment", "key": "PROJ-1", "title": "t",
            "body": "본문 %s\n----\n_wrapup 승인 게시 · %s_" % (i, i)}


def card(*ids):
    q = {"run_id": "r", "expires_at": EXP, "summary": "", "items": [item(i) for i in ids], "links": []}
    blocks = cardfmt.build_messages(q)[0]["blocks"]
    vals = {b["block_id"][:-4]: json.loads(b["elements"][0]["value"]) for b in blocks if b.get("block_id", "").endswith(":act")}
    return blocks, vals


class SlowJira:
    def __init__(self):
        self.added = []

    def find_tracked_comment(self, key, item_id):
        for k, body in self.added:
            if ("wrapup 승인 게시 · %s_" % item_id) in body:
                return "1"
        return None

    def add_comment(self, key, body):
        time.sleep(0.2)
        self.added.append((key, body))
        return str(len(self.added))


def test_concurrent_double_click_posts_once():
    blocks, vals = card("a")
    jira = SlowJira()
    p = Processor(ME, jira, dry_run=False)
    shown = []
    ts = [threading.Thread(target=p.process, args=("m1", blocks, vals["a"], ME, NOW, shown.append)) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(jira.added) == 1


def test_stale_snapshot_keeps_other_result():
    blocks, vals = card("a", "b")
    p = Processor(ME, SlowJira(), dry_run=False)
    shown = []
    p.process("m1", blocks, vals["a"], ME, NOW, shown.append)
    p.process("m1", blocks, vals["b"], ME, NOW, shown.append)  # 클릭 b 의 페이로드는 a 결과 이전 스냅샷
    final = shown[-1]
    ids = [b.get("block_id") for b in final]
    assert "a:res" in ids and "a:act" not in ids and "b:res" in ids


def test_not_allowed_user_does_not_touch_card():
    blocks, vals = card("a")
    p = Processor(ME, SlowJira(), dry_run=False)
    shown = []
    r = p.process("m1", blocks, vals["a"], "U_X", NOW, shown.append)
    assert shown == [] and r.text == "🚫 권한 없음"
