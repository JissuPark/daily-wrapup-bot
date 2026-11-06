"""카드 항목의 버튼 자리를 결과 문구로 바꾼다(slack_bolt 없이 테스트 가능)."""
from typing import List


def replace_actions(blocks: List[dict], item_id: str, text: str, keep_button: bool) -> List[dict]:
    act, res = item_id + ":act", item_id + ":res"
    result = {"type": "context", "block_id": res, "elements": [{"type": "mrkdwn", "text": text}]}
    out = []
    for b in blocks:
        bid = b.get("block_id")
        if bid == res:
            continue
        if bid == act:
            if keep_button:
                out.append(b)
            out.append(result)
            continue
        out.append(b)
    return out
