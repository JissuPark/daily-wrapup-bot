"""한 줄 로그. WRAPUP_BOT_LOG 가 있으면 그 파일에 UTF-8 로 바로 덧붙이고, 없으면 stdout."""
import os
from datetime import datetime


def log(*parts):
    line = " ".join([datetime.now().strftime("%Y-%m-%d %H:%M:%S")] + [str(p) for p in parts])
    path = os.environ.get("WRAPUP_BOT_LOG")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            return
        except OSError:  # 다른 프로세스가 잡고 있어도 봇은 계속 돈다
            pass
    print(line, flush=True)
