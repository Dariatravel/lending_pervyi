#!/bin/bash
# Сохранить параметры VPS в локальный файл (не коммитится в git).
set -euo pipefail

TARGET="${VPS_ENV_FILE:-/Users/darya_botova/abhazbereg-bot/.env.vps.local}"
PASS="$(pbpaste -Prefer txt 2>/dev/null || pbpaste)"
HOST="${VPS_HOST:-}"
USER_NAME="${VPS_USER:-}"

if [ -z "${PASS//[[:space:]]/}" ]; then
  echo "Буфер обмена пуст или там не текст." >&2
  echo "Скопируйте пароль VPS, затем запустите снова." >&2
  exit 1
fi

if [ -z "${HOST//[[:space:]]/}" ] || [ -z "${USER_NAME//[[:space:]]/}" ]; then
  echo "Перед запуском задайте VPS_HOST и VPS_USER в окружении." >&2
  echo "Пример: VPS_HOST='...' VPS_USER='...' tools/save_vps_password.sh" >&2
  exit 1
fi

umask 077
printf 'VPS_HOST=%s\nVPS_USER=%s\nVPS_PASSWORD=%s\n' "$HOST" "$USER_NAME" "$PASS" > "$TARGET"
chmod 600 "$TARGET"
echo "Сохранено: $TARGET"
