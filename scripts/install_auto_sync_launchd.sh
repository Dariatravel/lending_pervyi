#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/darya_botova/Documents/New project"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
PIPELINE_SCRIPT="$PROJECT_DIR/scripts/run_auto_sync_pipeline.py"
AGENT_ID="ru.abhazbereg.autosync"
PLIST_PATH="$HOME/Library/LaunchAgents/${AGENT_ID}.plist"
LOG_DIR="$PROJECT_DIR/output/auto-sync/launchd"
OUT_LOG="$LOG_DIR/stdout.log"
ERR_LOG="$LOG_DIR/stderr.log"

INTERVAL_SECONDS="${1:-10800}" # по умолчанию каждые 3 часа

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Не найден python из .venv: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -f "$PIPELINE_SCRIPT" ]]; then
  echo "Не найден скрипт пайплайна: $PIPELINE_SCRIPT" >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>${AGENT_ID}</string>

    <key>ProgramArguments</key>
    <array>
      <string>${PYTHON_BIN}</string>
      <string>${PIPELINE_SCRIPT}</string>
      <string>--mode</string>
      <string>full</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>

    <key>RunAtLoad</key>
    <true/>

    <key>StartInterval</key>
    <integer>${INTERVAL_SECONDS}</integer>

    <key>StandardOutPath</key>
    <string>${OUT_LOG}</string>
    <key>StandardErrorPath</key>
    <string>${ERR_LOG}</string>
  </dict>
</plist>
PLIST

launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl load "$PLIST_PATH"

echo "Готово."
echo "LaunchAgent: $PLIST_PATH"
echo "Интервал: ${INTERVAL_SECONDS} сек."
echo "Логи:"
echo "  $OUT_LOG"
echo "  $ERR_LOG"
echo
echo "Проверка статуса:"
echo "  launchctl list | grep ${AGENT_ID}"
