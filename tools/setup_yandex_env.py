#!/usr/bin/env python3
"""Заполнить .env.yandex.local из буфера обмена (macOS: pbpaste). Секреты в git не попадают."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env.yandex.local"
EXAMPLE_PATH = ROOT / ".env.yandex.example"


def clipboard_text() -> str:
    try:
        return subprocess.check_output(["pbpaste"], text=True).strip()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"Не удалось прочитать буфер: {exc}", file=sys.stderr)
        sys.exit(1)


def prompt(label: str) -> str:
    print()
    print(label)
    input("→ Когда скопировали — нажмите Enter… ")
    value = clipboard_text()
    if not value or value.startswith("your_"):
        print("Буфер пуст или там placeholder. Скопируйте реальный ключ и повторите.")
        sys.exit(1)
    if len(value) > 200 or "\n" in value:
        print("В буфере слишком много текста (нужна одна строка ключа). Скопируйте только Key ID или Secret.")
        sys.exit(1)
    return value


def write_env(access_key: str, secret_key: str) -> None:
    template = EXAMPLE_PATH.read_text(encoding="utf-8") if EXAMPLE_PATH.is_file() else ""
    lines: list[str] = []
    for raw in template.splitlines():
        if raw.startswith("YANDEX_S3_ACCESS_KEY_ID="):
            lines.append(f"YANDEX_S3_ACCESS_KEY_ID={access_key}")
        elif raw.startswith("YANDEX_S3_SECRET_ACCESS_KEY="):
            lines.append(f"YANDEX_S3_SECRET_ACCESS_KEY={secret_key}")
        else:
            lines.append(raw)
    if not lines:
        lines = [
            f"YANDEX_S3_ACCESS_KEY_ID={access_key}",
            f"YANDEX_S3_SECRET_ACCESS_KEY={secret_key}",
            "YANDEX_S3_BUCKET=abhazbereg-media",
            "YANDEX_S3_ENDPOINT=https://storage.yandexcloud.net",
            "YANDEX_S3_REGION=ru-central1",
        ]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    print("Настройка .env.yandex.local (файл в .gitignore, ключи не уйдут в репозиторий)")
    print()
    print("Сначала получите ключи в Yandex Cloud (см. инструкцию в чате).")
    print("Потом по очереди копируйте Key ID и Secret в буфер — скрипт подставит их сам.")

    access_key = prompt("1/2  Скопируйте **Идентификатор ключа** (Key ID) в буфер.")
    secret_key = prompt("2/2  Скопируйте **Секретный ключ** (Secret) в буфер.")

    write_env(access_key, secret_key)
    print()
    print(f"Готово: {ENV_PATH}")
    print("Проверка (dry-run):")
    print("  python3 tools/upload_yandex_media.py --dry-run --workers 48 media/cards media/hotels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
