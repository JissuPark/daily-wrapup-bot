import hashlib
import json
from datetime import datetime

import pytest

from wrapup_bot import cardfmt

EXP = "2026-11-06T20:10:00+09:00"


def queue(items, links=None):
    return {"run_id": "2026-11-05", "created_at": "2026-11-05T21:10:00+09:00",
            "expires_at": EXP, "summary": "게시 대기 1건", "items": items,
            "links": links or []}


def comment(body, id_="2026-11-05-01"):
    return {"id": id_, "kind": "comment", "key": "PROJ-1", "title": "t", "body": body}


def all_blocks(msgs):
    return [b for m in msgs for b in m["blocks"]]


def button_value(blocks, id_):
    for b in blocks:
        if b.get("block_id") == id_ + ":act":
            return json.loads(b["elements"][0]["value"])
    raise AssertionError("no button")


def roundtrip(body):
    msgs = cardfmt.build_messages(queue([comment(body)]))
    blocks = all_blocks(msgs)
    return blocks, cardfmt.extract_body(blocks, "2026-11-05-01")


def test_roundtrip_basic():
    body = "*굵게* 진행 {{code}} [제목|https://x]\n* 목록 하나"
    blocks, got = roundtrip(body)
    assert got == cardfmt.normalize(body)
    v = button_value(blocks, "2026-11-05-01")
    assert v["sha256"] == cardfmt.item_hash(comment(body))
    assert v["key"] == "PROJ-1" and v["kind"] == "comment" and v["expires_at"] == EXP


def test_roundtrip_normalizes_whitespace():
    body = "a  \r\n\r\nb\t\n\n"
    blocks, got = roundtrip(body)
    assert got == "a\n\nb"
    assert button_value(blocks, "2026-11-05-01")["sha256"] == hashlib.sha256("a\n\nb".encode()).hexdigest()


def test_roundtrip_preserves_literal_entities():
    body = "x &lt; y & <z> &amp;"
    _, got = roundtrip(body)
    assert got == body


def test_split_long_body_with_emoji():
    body = ("가나다&😀<" * 1000)[:6000]
    blocks, got = roundtrip(body)
    parts = [b for b in blocks if b.get("block_id", "").startswith("2026-11-05-01:p")]
    assert len(parts) >= 3
    assert all(len(b["text"]["text"]) <= 3000 for b in parts)
    assert got == cardfmt.normalize(body)


def test_reject_code_fence():
    with pytest.raises(ValueError):
        cardfmt.build_messages(queue([comment("a ``` b")]))


def test_transition_item():
    it = {"id": "2026-11-05-02", "kind": "transition", "key": "PROJ-1", "title": "t", "to_status": "진행 중"}
    blocks = all_blocks(cardfmt.build_messages(queue([it])))
    assert not [b for b in blocks if b.get("block_id", "").startswith("2026-11-05-02:p")]
    assert button_value(blocks, "2026-11-05-02")["sha256"] == hashlib.sha256("PROJ-1|진행 중".encode()).hexdigest()
    assert button_value(blocks, "2026-11-05-02")["to_status"] == "진행 중"


def test_messages_split_under_50_blocks():
    items = [comment("본문 %d" % i, "id-%02d" % i) for i in range(30)]
    msgs = cardfmt.build_messages(queue(items, [{"title": "문서", "url": "https://c"}]))
    assert len(msgs) >= 2
    assert all(len(m["blocks"]) <= 50 for m in msgs)
    assert "게시 대기 1건" in json.dumps(msgs[0], ensure_ascii=False)
    assert all("게시 대기 1건" not in json.dumps(m, ensure_ascii=False) for m in msgs[1:])
    for i in range(30):
        assert cardfmt.extract_body(all_blocks(msgs), "id-%02d" % i) == "본문 %d" % i


def test_is_expired_timezone():
    assert cardfmt.is_expired(EXP, datetime.fromisoformat("2026-11-06T11:09:00+00:00")) is False
    assert cardfmt.is_expired(EXP, datetime.fromisoformat("2026-11-06T11:11:00+00:00")) is True


def test_body_sections_are_verbatim():
    blocks, _ = roundtrip("https://example.com @here <!channel>")
    parts = [b for b in blocks if b.get("block_id", "").startswith("2026-11-05-01:p")]
    assert parts and all(b["text"].get("verbatim") is True for b in parts)
