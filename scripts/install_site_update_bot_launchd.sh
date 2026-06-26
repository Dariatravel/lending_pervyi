#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi

BOT_SCRIPT="$PROJECT_DIR/scripts/site_update_bot.py"
ENV_FILE="$PROJECT_DIR/.env.site-update-bot"
AGENT_ID="ru.abhazbereg.site-update-bot"
PLIST_PATH="$HOME/Library/LaunchAgents/${AGENT_ID}.plist"
LOG_DIR="$PROJECT_DIR/output/site-update-bot/launchd"
OUT_LOG="$LOG_DIR/stdout.log"
ERR_LOG="$LOG_DIR/stderr.log"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Не найден python: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -f "$BOT_SCRIPT" ]]; then
  echo "Не найден скрипт бота: $BOT_SCRIPT" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Не найден локальный env: $ENV_FILE" >&2
  echo "Создайте его из .env.site-update-bot.example и заполните токен/chat_id." >&2
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
      <string>${BOT_SCRIPT}</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>${OUT_LOG}</string>
    <key>StandardErrorPath</key>
    <string>${ERR_LOG}</string>
  </dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl kickstart -k "gui/$(id -u)/${AGENT_ID}"

echo "Готово."
echo "LaunchAgent: $PLIST_PATH"
echo "Label: $AGENT_ID"
echo "Python: $PYTHON_BIN"
echo "Логи:"
echo "  $OUT_LOG"
echo "  $ERR_LOG"
echo
echo "Проверка:"
echo "  launchctl print gui/$(id -u)/${AGENT_ID}"
