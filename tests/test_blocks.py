from wrapup_bot.blocks import replace_actions


def blocks():
    return [
        {"type": "section", "block_id": "a", "text": {"type": "mrkdwn", "text": "A"}},
        {"type": "actions", "block_id": "a:act", "elements": [{"type": "button"}]},
        {"type": "section", "block_id": "b", "text": {"type": "mrkdwn", "text": "B"}},
        {"type": "actions", "block_id": "b:act", "elements": [{"type": "button"}]},
    ]


def ids(bs):
    return [b["block_id"] for b in bs]


def test_replace_keeps_other_items():
    out = replace_actions(blocks(), "a", "✅ 게시 #1", keep_button=False)
    assert ids(out) == ["a", "a:res", "b", "b:act"]
    assert out[1]["type"] == "context" and out[1]["elements"][0]["text"] == "✅ 게시 #1"


def test_retry_keeps_button():
    out = replace_actions(blocks(), "a", "❌ HTTP 500 — 다시 누를 수 있음", keep_button=True)
    assert ids(out) == ["a", "a:act", "a:res", "b", "b:act"]


def test_previous_result_replaced():
    first = replace_actions(blocks(), "a", "🧪 DRY-RUN", keep_button=True)
    out = replace_actions(first, "a", "✅ 게시 #1", keep_button=False)
    assert ids(out) == ["a", "a:res", "b", "b:act"]
    assert out[1]["elements"][0]["text"] == "✅ 게시 #1"
