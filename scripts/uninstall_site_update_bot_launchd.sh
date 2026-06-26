#!/usr/bin/env bash
set -euo pipefail

AGENT_ID="ru.abhazbereg.site-update-bot"
PLIST_PATH="$HOME/Library/LaunchAgents/${AGENT_ID}.plist"

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 || true

if [[ -f "$PLIST_PATH" ]]; then
  rm -f "$PLIST_PATH"
  echo "Удалено: $PLIST_PATH"
else
  echo "LaunchAgent не найден: $PLIST_PATH"
fi

echo "Проверка:"
echo "  launchctl print gui/$(id -u)/${AGENT_ID}"
