"""wrapup 큐 → Slack 승인 카드(Incoming Webhook). 표준 라이브러리만.

사용: python send_cards.py <queue.json> [--print]
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wrapup_bot.cardfmt import build_messages  # noqa: E402

ENV = "WRAPUP_SLACK_WEBHOOK_URL"


def _post(url, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=15) as r:
        if r.status != 200:
            raise RuntimeError("HTTP %d" % r.status)


DEFAULT_ENV_FILE = os.path.join(os.path.expanduser("~"), ".config", "wrapup-bot", "env")


def _url_from_file(path):
    """env 파일에서 웹훅 URL 한 줄만 읽는다(다른 값은 읽지 않는다)."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith(ENV + "="):
                    return line.split("=", 1)[1].strip() or None
    except OSError:
        return None
    return None


def main(argv, post=None, env_file=DEFAULT_ENV_FILE):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        sys.stderr.write("사용: send_cards.py <queue.json> [--print]\n")
        return 2
    with open(args[0], encoding="utf-8") as f:
        queue = json.load(f)
    if not (queue.get("items") or queue.get("links")):
        print("전송할 항목 없음")
        return 0
    msgs = build_messages(queue)
    if "--print" in argv:
        print(json.dumps(msgs, ensure_ascii=False, indent=1))
        return 0
    url = os.environ.get(ENV) or (env_file and _url_from_file(env_file))
    if not url:
        sys.stderr.write("%s 가 환경변수·env 파일 어디에도 없다\n" % ENV)
        return 2
    post = post or _post
    try:
        for m in msgs:
            post(url, m)
    except Exception as e:  # 실패 사유만 남기고 URL 은 남기지 않는다
        sys.stderr.write("전송 실패: %s\n" % type(e).__name__)
        return 1
    print("전송 %d개 메시지" % len(msgs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
