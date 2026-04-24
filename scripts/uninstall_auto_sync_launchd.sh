#!/usr/bin/env bash
set -euo pipefail

AGENT_ID="ru.abhazbereg.autosync"
PLIST_PATH="$HOME/Library/LaunchAgents/${AGENT_ID}.plist"

if [[ -f "$PLIST_PATH" ]]; then
  launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
  rm -f "$PLIST_PATH"
  echo "Удалено: $PLIST_PATH"
else
  echo "LaunchAgent не найден: $PLIST_PATH"
fi

echo "Проверка:"
echo "  launchctl list | grep ${AGENT_ID} || true"
