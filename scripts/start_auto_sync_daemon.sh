#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/darya_botova/Documents/New project"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
PIPELINE="$PROJECT_DIR/scripts/run_auto_sync_pipeline.py"
PID_FILE="$PROJECT_DIR/output/auto-sync/daemon.pid"
LOG_DIR="$PROJECT_DIR/output/auto-sync/daemon"
OUT_LOG="$LOG_DIR/stdout.log"
ERR_LOG="$LOG_DIR/stderr.log"
INTERVAL_SECONDS="${1:-10800}" # 3 часа по умолчанию

mkdir -p "$LOG_DIR"

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "${OLD_PID}" 2>/dev/null; then
    echo "Демон уже запущен, PID=${OLD_PID}"
    exit 0
  fi
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Не найден python: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -f "$PIPELINE" ]]; then
  echo "Не найден пайплайн: $PIPELINE" >&2
  exit 1
fi

nohup /bin/bash -lc "
  cd \"$PROJECT_DIR\"
  while true; do
    \"$PYTHON_BIN\" \"$PIPELINE\" --mode full >> \"$OUT_LOG\" 2>> \"$ERR_LOG\"
    sleep \"$INTERVAL_SECONDS\"
  done
" >/dev/null 2>&1 &

echo $! > "$PID_FILE"
echo "Демон запущен. PID=$(cat "$PID_FILE")"
echo "Логи:"
echo "  $OUT_LOG"
echo "  $ERR_LOG"
