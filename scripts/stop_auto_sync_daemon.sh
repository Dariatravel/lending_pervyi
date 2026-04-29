#!/usr/bin/env bash
set -euo pipefail

PID_FILE="/Users/darya_botova/Documents/New project/output/auto-sync/daemon.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "PID-файл не найден: $PID_FILE"
  exit 0
fi

PID="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ -z "$PID" ]]; then
  rm -f "$PID_FILE"
  echo "PID пустой, PID-файл удален."
  exit 0
fi

if kill -0 "$PID" 2>/dev/null; then
  kill "$PID" || true
  sleep 1
  if kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID" || true
  fi
  echo "Демон остановлен. PID=$PID"
else
  echo "Процесс PID=$PID уже не запущен."
fi

rm -f "$PID_FILE"
