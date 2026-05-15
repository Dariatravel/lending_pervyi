#!/usr/bin/env python3
"""
Перенести только НОВЫЕ объекты: строки «СОЦСЕТИ», которых ещё нет в базе как пара (канал + id поста).

Используется прежняя логика: scripts/backfill_missing_from_sheet_links.py
(materialize_object, медиа в Storage и т.д.).

После добавления строк с фильтрами в таблице:
  фильтры в Supabase — apply_all_filters_from_sheet.py
  карточки каталога — rebuild_from_supabase.py
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Новые объекты только из таблицы (без полного синка канала).")
    parser.add_argument("--skip-filters", action="store_true", help="Не применять фильтры из таблицы.")
    parser.add_argument("--skip-rebuild", action="store_true", help="Не пересобирать index.html / kvartira.")
    parser.add_argument("--skip-verify", action="store_true", help="Не запускать verify_object_media.")
    args = parser.parse_args()

    env_path = ROOT / ".env.supabase.local"
    if not env_path.exists():
        print("Нет .env.supabase.local", file=sys.stderr)
        return 2

    env = os.environ.copy()
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

    cred = env.get("GOOGLE_SERVICE_ACCOUNT_JSON") or str(ROOT / "google-service-account.json")
    if Path(cred).exists():
        env["GOOGLE_SERVICE_ACCOUNT_JSON"] = cred

    cmds: list[list[str]] = [
        [sys.executable, str(ROOT / "scripts" / "backfill_missing_from_sheet_links.py")],
    ]
    if not args.skip_filters:
        cmds.append([sys.executable, str(ROOT / "scripts" / "apply_all_filters_from_sheet.py")])
    if not args.skip_rebuild:
        cmds.append([sys.executable, str(ROOT / "scripts" / "rebuild_from_supabase.py")])
    if not args.skip_verify:
        cmds.append([sys.executable, str(ROOT / "tools" / "verify_object_media.py")])

    for cmd in cmds:
        print("+", " ".join(cmd), flush=True)
        rc = subprocess.run(cmd, cwd=str(ROOT), env=env, check=False).returncode
        if rc != 0:
            print(f"Ошибка ({rc}): {' '.join(cmd)}", file=sys.stderr)
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
