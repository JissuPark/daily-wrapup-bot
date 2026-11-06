import json
import os
import sys

import send_cards

HERE = os.path.dirname(__file__)
SAMPLE = os.path.join(HERE, "fixtures", "queue_sample.json")


def test_print_mode_no_post(capsys, monkeypatch):
    calls = []
    monkeypatch.setenv("WRAPUP_SLACK_WEBHOOK_URL", "https://hooks.example/x")
    rc = send_cards.main([SAMPLE, "--print"], post=lambda u, p: calls.append(p))
    assert rc == 0 and calls == []
    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, list) and out[0]["blocks"]


def test_posts_each_message(monkeypatch):
    calls = []
    monkeypatch.setenv("WRAPUP_SLACK_WEBHOOK_URL", "https://hooks.example/x")
    rc = send_cards.main([SAMPLE], post=lambda u, p: calls.append((u, p)))
    assert rc == 0 and len(calls) >= 1
    assert calls[0][0] == "https://hooks.example/x"


def test_missing_env_returns_2(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("WRAPUP_SLACK_WEBHOOK_URL", raising=False)
    assert send_cards.main([SAMPLE], post=lambda u, p: None, env_file=str(tmp_path / "none")) == 2
    assert "WRAPUP_SLACK_WEBHOOK_URL" in capsys.readouterr().err


def test_empty_queue_skips(tmp_path, monkeypatch):
    q = tmp_path / "q.json"
    q.write_text(json.dumps({"run_id": "x", "expires_at": "2026-11-07T00:00:00+09:00", "items": [], "links": []}), encoding="utf-8")
    calls = []
    monkeypatch.setenv("WRAPUP_SLACK_WEBHOOK_URL", "https://hooks.example/x")
    assert send_cards.main([str(q)], post=lambda u, p: calls.append(p)) == 0
    assert calls == []


def test_post_failure_returns_1(monkeypatch):
    monkeypatch.setenv("WRAPUP_SLACK_WEBHOOK_URL", "https://hooks.example/x")

    def boom(u, p):
        raise RuntimeError("HTTP 500")
    assert send_cards.main([SAMPLE], post=boom) == 1


def test_env_file_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("WRAPUP_SLACK_WEBHOOK_URL", raising=False)
    f = tmp_path / "env"
    f.write_text("# c\nSLACK_BOT_TOKEN=xoxb-no\nWRAPUP_SLACK_WEBHOOK_URL=https://hooks.example/f\n", encoding="utf-8")
    calls = []
    assert send_cards.main([SAMPLE], post=lambda u, p: calls.append(u), env_file=str(f)) == 0
    assert calls and calls[0] == "https://hooks.example/f"


def test_env_var_wins_over_file(tmp_path, monkeypatch):
    monkeypatch.setenv("WRAPUP_SLACK_WEBHOOK_URL", "https://hooks.example/env")
    f = tmp_path / "env"
    f.write_text("WRAPUP_SLACK_WEBHOOK_URL=https://hooks.example/f\n", encoding="utf-8")
    calls = []
    send_cards.main([SAMPLE], post=lambda u, p: calls.append(u), env_file=str(f))
    assert calls[0] == "https://hooks.example/env"
