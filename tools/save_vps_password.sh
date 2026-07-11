#!/bin/bash
# Сохранить root-пароль Timeweb VPS в локальный файл (не коммитится в git).
set -euo pipefail

TARGET="${VPS_ENV_FILE:-/Users/darya_botova/abhazbereg-bot/.env.vps.local}"
PASS="$(pbpaste -Prefer txt 2>/dev/null || pbpaste)"

if [ -z "${PASS//[[:space:]]/}" ]; then
  echo "Буфер обмена пуст или там не текст." >&2
  echo "Скопируйте пароль в Timeweb (кнопка «Скопировать» у root-пароля), затем запустите снова." >&2
  exit 1
fi

umask 077
printf 'VPS_HOST=81.31.247.74\nVPS_USER=root\nVPS_PASSWORD=%s\n' "$PASS" > "$TARGET"
chmod 600 "$TARGET"
echo "Сохранено: $TARGET"
