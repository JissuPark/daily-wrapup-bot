"""wrapup 승인 봇 — Slack Socket Mode. 실행: python -m wrapup_bot.app

환경변수: SLACK_BOT_TOKEN SLACK_APP_TOKEN JIRA_BASE_URL JIRA_EMAIL JIRA_API_TOKEN ALLOWED_USER_ID DRY_RUN
"""
import json
import os
import sys
from datetime import datetime, timezone

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from wrapup_bot.jira import Jira
from wrapup_bot.logutil import log
from wrapup_bot.processor import Processor

REQUIRED = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "ALLOWED_USER_ID"]


def build_app(env) -> App:
    allowed = env["ALLOWED_USER_ID"]
    dry_run = env.get("DRY_RUN", "1") != "0"
    jira = Jira(env["JIRA_BASE_URL"], env["JIRA_EMAIL"], env["JIRA_API_TOKEN"])
    proc = Processor(allowed, jira, dry_run)
    app = App(token=env["SLACK_BOT_TOKEN"])

    @app.action("approve")
    def on_approve(ack, body, respond):
        ack()
        value = json.loads(body["actions"][0]["value"])
        user = body["user"]["id"]
        msg = body.get("message") or {}
        text = msg.get("text") or ""

        def show(blocks):
            respond(replace_original=True, text=text, blocks=blocks)

        res = proc.process(msg.get("ts", ""), msg.get("blocks") or [], value, user,
                           datetime.now(timezone.utc), show)
        if user != allowed:
            respond(response_type="ephemeral", replace_original=False, text=res.text)
        log(value.get("id"), value.get("key"), value.get("kind"), res.text, user)

    return app


def main() -> int:
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        sys.stderr.write("환경변수 없음: %s\n" % " ".join(missing))
        return 2
    app = build_app(os.environ)
    log("시작", "DRY_RUN" if os.environ.get("DRY_RUN", "1") != "0" else "LIVE")
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
