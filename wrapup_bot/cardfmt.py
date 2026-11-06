"""카드 규칙 — 송신(PC)·수신(서버)이 같이 쓴다. 표준 라이브러리만."""
import hashlib
import json
from datetime import datetime
from typing import List, Optional

PART_LIMIT = 2900  # Slack section 3000자 한도에서 ``` 감싸기 여유
MAX_BLOCKS = 50
FENCE = "```"
KIND_LABEL = {"comment": "코멘트", "transition": "상태 전환"}


def normalize(body: str) -> str:
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(l.rstrip() for l in lines).strip("\n")


def item_hash(item: dict) -> str:
    if item["kind"] == "transition":
        raw = "%s|%s" % (item["key"], item["to_status"])
    else:
        raw = normalize(item["body"])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def slack_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def slack_unescape(s: str) -> str:
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def _split(text: str) -> List[str]:
    parts, cur, size = [], [], 0
    for ch in text:
        n = len(slack_escape(ch))
        if size + n > PART_LIMIT:
            parts.append("".join(cur))
            cur, size = [], 0
        cur.append(ch)
        size += n
    if cur:
        parts.append("".join(cur))
    return parts or [""]


def _section(text: str, block_id: Optional[str] = None, verbatim: bool = False) -> dict:
    b = {"type": "section", "text": {"type": "mrkdwn", "text": text}}
    if verbatim:  # URL 자동 링크·멘션 해석을 막아 원문이 그대로 돌아오게
        b["text"]["verbatim"] = True
    if block_id:
        b["block_id"] = block_id
    return b


def _item_blocks(item: dict, expires_at: str) -> List[dict]:
    kind = item["kind"]
    if kind not in KIND_LABEL:
        raise ValueError("알 수 없는 kind: %s" % kind)
    title = "*%s* · %s · %s" % (slack_escape(item["key"]), KIND_LABEL[kind], slack_escape(item.get("title", "")))
    blocks = []
    if kind == "transition":
        title += " → *%s*" % slack_escape(item["to_status"])
        blocks.append(_section(title, item["id"]))
    else:
        body = normalize(item["body"])
        if FENCE in body:
            raise ValueError("원문에 코드 블록(```)이 있다: %s" % item["id"])
        blocks.append(_section(title, item["id"]))
        for n, part in enumerate(_split(body), 1):
            blocks.append(_section(FENCE + "\n" + slack_escape(part) + "\n" + FENCE, "%s:p%d" % (item["id"], n), verbatim=True))
    value = {"id": item["id"], "kind": kind, "key": item["key"], "to_status": item.get("to_status"),
             "expires_at": expires_at, "sha256": item_hash(item)}
    blocks.append({"type": "actions", "block_id": item["id"] + ":act", "elements": [{
        "type": "button", "action_id": "approve", "style": "primary",
        "text": {"type": "plain_text", "text": "승인"},
        "value": json.dumps(value, ensure_ascii=False)}]})
    return blocks


def build_messages(queue: dict) -> List[dict]:
    header = [_section("*wrapup %s* 승인 대기\n%s" % (slack_escape(queue["run_id"]), slack_escape(queue.get("summary", "")))),
              {"type": "context", "elements": [{"type": "mrkdwn", "text": "만료 %s · 안 누르면 볼트에 이월" % queue["expires_at"]}]}]
    links = queue.get("links") or []
    link_block = []
    if links:
        lines = ["• <%s|%s>" % (l["url"], slack_escape(l["title"]).replace("|", "¦")) for l in links]
        link_block = [_section("*Confluence (링크만)*\n" + "\n".join(lines))]

    groups, cur = [], list(header)
    for item in queue.get("items") or []:
        ib = _item_blocks(item, queue["expires_at"])
        if len(ib) > MAX_BLOCKS - 1:
            raise ValueError("항목이 너무 길다: %s" % item["id"])
        if len(cur) + len(ib) > MAX_BLOCKS:
            groups.append(cur)
            cur = []
        cur.extend(ib)
    if len(cur) + len(link_block) > MAX_BLOCKS:
        groups.append(cur)
        cur = []
    cur.extend(link_block)
    groups.append(cur)
    text = "wrapup %s 승인 대기 %d건" % (queue["run_id"], len(queue.get("items") or []))
    return [{"text": text, "blocks": g} for g in groups if g]


def extract_body(blocks: List[dict], item_id: str) -> Optional[str]:
    prefix = item_id + ":p"
    parts = []
    for b in blocks:
        bid = b.get("block_id", "")
        if bid.startswith(prefix) and bid[len(prefix):].isdigit():
            text = b["text"]["text"]
            if not (text.startswith(FENCE + "\n") and text.endswith("\n" + FENCE)):
                return None
            parts.append((int(bid[len(prefix):]), slack_unescape(text[len(FENCE) + 1:-len(FENCE) - 1])))
    if not parts:
        return None
    return normalize("".join(p for _, p in sorted(parts)))


def is_expired(expires_at: str, now: datetime) -> bool:
    exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    return now > exp
