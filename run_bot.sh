#!/bin/sh
# wrapup 승인 봇 실행. crontab: */5 * * * * flock -n /tmp/wrapup-bot-$USER.lock <레포>/run_bot.sh
ENV_FILE="$HOME/.config/wrapup-bot/env"
REPO="$(cd "$(dirname "$0")" && pwd)"
LOG="$HOME/wrapup-bot.log"

if [ ! -f "$ENV_FILE" ]; then
  echo "env 파일 없음: $ENV_FILE" >&2; exit 1
fi
PERM="$(stat -c %a "$ENV_FILE")"
if [ "$PERM" != "600" ]; then
  echo "env 파일 권한이 $PERM — 600 이어야 한다" >&2; exit 1
fi

set -a
. "$ENV_FILE"
set +a
cd "$REPO" || exit 1
exec "$REPO/.venv/bin/python" -m wrapup_bot.app >> "$LOG" 2>&1
