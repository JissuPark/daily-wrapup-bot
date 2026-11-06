"""클릭 직렬화 + 메시지별 최신 블록 보관.

- 클릭을 하나씩 처리한다(전역 락) — 동시에 들어온 이중 클릭도 두 번째는 멱등 확인에서 걸린다.
- 클릭 페이로드의 블록은 그 순간 스냅샷이라, 앞 클릭의 결과를 모를 수 있다.
  그래서 이 프로세스가 마지막으로 그린 블록을 메시지(ts)별로 들고 있다가 그걸 기준으로 고친다.
- 락은 프로세스 안에서만 유효하다 → 봇은 한 프로세스만 띄운다(run_bot.sh 는 flock 으로 실행).
"""
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Callable, List

from wrapup_bot.blocks import replace_actions
from wrapup_bot.handler import Result, handle_approval

CACHE_SIZE = 50


class Processor:
    def __init__(self, allowed_user_id: str, jira, dry_run: bool):
        self.allowed, self.jira, self.dry_run = allowed_user_id, jira, dry_run
        self._lock = threading.Lock()
        self._latest = OrderedDict()

    def process(self, ts: str, payload_blocks: List[dict], value: dict, user_id: str,
                now: datetime, show: Callable[[List[dict]], None]) -> Result:
        if user_id != self.allowed:
            return Result("🚫 권한 없음", True)
        with self._lock:
            blocks = self._latest.get(ts) or payload_blocks
            show(replace_actions(blocks, value["id"], "⏳ 처리 중", keep_button=False))
            try:
                res = handle_approval(value, blocks, user_id, now, self.allowed, self.jira, self.dry_run)
            except Exception as e:  # 예상 못 한 오류도 버튼은 되살린다
                res = Result("❌ 내부 오류 %s — 다시 누를 수 있음" % type(e).__name__, True)
            final = replace_actions(blocks, value["id"], res.text, keep_button=res.retry)
            self._latest[ts] = final
            self._latest.move_to_end(ts)
            while len(self._latest) > CACHE_SIZE:
                self._latest.popitem(last=False)
            show(final)
            return res
