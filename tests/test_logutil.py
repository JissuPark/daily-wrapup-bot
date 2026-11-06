from wrapup_bot.logutil import log


def test_log_appends_utf8_to_file(tmp_path, monkeypatch):
    f = tmp_path / "bot.log"
    monkeypatch.setenv("WRAPUP_BOT_LOG", str(f))
    log("live-01", "✅ 게시 #1")
    log("live-02", "⏭ 이미 진행 중")
    lines = f.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and lines[0].endswith("live-01 ✅ 게시 #1")


def test_log_prints_without_env(capsys, monkeypatch):
    monkeypatch.delenv("WRAPUP_BOT_LOG", raising=False)
    log("a", "b")
    assert capsys.readouterr().out.strip().endswith("a b")


def test_log_survives_unwritable_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WRAPUP_BOT_LOG", str(tmp_path))  # 디렉터리라 열 수 없다
    log("x", "y")
    assert capsys.readouterr().out.strip().endswith("x y")
