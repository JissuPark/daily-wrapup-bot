# wrapup-slack-bot

wrapup 의 Jira 게시 대기를 Slack 카드로 보내고, [승인]을 누른 항목만 원문 그대로 Jira 에 올린다.

| 파일 | 역할 | 실행 위치 |
|---|---|---|
| `send_cards.py` | 큐 JSON → 카드(웹훅) | PC |
| `wrapup_bot/cardfmt.py` | 카드 규칙(정규화·이스케이프·분할·해시·복원) | 양쪽 |
| `wrapup_bot/handler.py` | 승인 판단(사용자→만료→해시→멱등→게시) | 서버 |
| `wrapup_bot/jira.py` | Jira REST v2(코멘트·전환) | 서버 |
| `wrapup_bot/app.py` | Slack Socket Mode | 서버 |

## PC: 카드 보내기

```bash
python send_cards.py tests/fixtures/queue_sample.json --print
```
```bash
python send_cards.py <큐 파일>
```
웹훅 URL 은 사용자 환경변수 `WRAPUP_SLACK_WEBHOOK_URL` 에 둔다(파일·볼트에 쓰지 않는다).

## 서버 배포 (개인 계정 — 공용 계정 금지)

1. 코드 전송 후 무결성 확인(PC 와 같은 값이어야 한다)
   ```bash
   find wrapup_bot send_cards.py run_bot.sh requirements.txt -type f | sort | xargs sha256sum
   ```
2. venv
   ```bash
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```
3. env 파일 `~/.config/wrapup-bot/env` (권한 600)
   ```
   SLACK_BOT_TOKEN=
   SLACK_APP_TOKEN=
   JIRA_BASE_URL=https://your-site.atlassian.net
   JIRA_EMAIL=
   JIRA_API_TOKEN=
   ALLOWED_USER_ID=
   DRY_RUN=1
   ```
   ```bash
   mkdir -p ~/.config/wrapup-bot && chmod 700 ~/.config/wrapup-bot && chmod 600 ~/.config/wrapup-bot/env
   ```
   `ALLOWED_USER_ID` = Slack 프로필 → ⋮ → "멤버 ID 복사"(`U…`).
4. 첫 실행 → `~/wrapup-bot.log` 에 `시작 DRY_RUN` 확인. **항상 flock 으로 띄운다** — 클릭 직렬화 락이 프로세스 안에서만 유효해서, 두 개가 뜨면 중복 게시를 못 막는다.
   ```bash
   chmod +x run_bot.sh && (flock -n /tmp/wrapup-bot-$USER.lock ./run_bot.sh &)
   ```
5. 상시 실행(죽으면 5분 안에 재기동)
   ```
   */5 * * * * flock -n /tmp/wrapup-bot-$USER.lock /절대경로/run_bot.sh
   ```
6. DRY-RUN 확인 뒤 `DRY_RUN=0` 으로 바꾸고 프로세스 재시작(`pkill -f wrapup_bot.app`, 크론이 다시 띄운다).

## PC(Windows) 상시 실행 — 현재 운영 방식

- 실행기: `run_bot.ps1` — env 파일(`%USERPROFILE%\.config\wrapup-bot\env`)을 프로세스 환경변수로 읽고, 봇이 죽으면 30초 뒤 다시 띄운다. 이름 있는 Mutex 로 한 PC 에 하나만 뜬다.
- 작업 스케줄러 `wrapup-slack-bot`: 로그온 시 시작, 실행 시간 제한 없음. 수동 재시작:
  ```powershell
  Stop-ScheduledTask wrapup-slack-bot; Start-ScheduledTask wrapup-slack-bot
  ```
- 로그: `%USERPROFILE%\wrapup-bot.log` (봇이 `WRAPUP_BOT_LOG` 로 바로 덧붙인다). 이 파일을 `tail -F` 로 오래 잡아 두지 않는다 — Windows 에서 쓰기가 막힐 수 있다.
- PC 가 꺼져 있거나 로그아웃 상태면 카드 버튼이 반응하지 않는다. 그때는 볼트 게시 대기를 `/jira-sync` 로 올린다.
- python.exe 가 두 개 보이는 건 정상이다(venv 실행기 + 실제 인터프리터).

## 결과 문구
`✅ 게시 #id` · `✅ <상태>(으)로 전환` · `⏭ 이미 …` · `⌛ 만료` · `❌ 원문 없음/불일치` · `🧪 DRY-RUN` · `❌ … — 다시 누를 수 있음`(버튼 유지)

## 테스트
```bash
python -m pytest -q
```
