#!/usr/bin/env python3
"""
Перенести только НОВЫЕ объекты: строки «СОЦСЕТИ», которых ещё нет в базе.

После добавления:
  фильтры — apply_all_filters_from_sheet.py (--snapshot-only без Supabase)
  каталог — rebuild_from_catalog_snapshot.py
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Новые объекты только из таблицы.")
    parser.add_argument("--skip-filters", action="store_true")
    parser.add_argument("--skip-rebuild", action="store_true")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument(
        "--snapshot-only",
        action="store_true",
        help="Не требовать Supabase; писать в catalog-snapshot.json (SKIP_SUPABASE_SYNC=1).",
    )
    args = parser.parse_args()

    env = os.environ.copy()
    snapshot_only = args.snapshot_only or env.get("SKIP_SUPABASE_SYNC", "").strip().lower() in {"1", "true", "yes", "on"}

    env_path = ROOT / ".env.supabase.local"
    if snapshot_only:
        if not SNAPSHOT_PATH.exists():
            print("Нет data/catalog-snapshot.json для --snapshot-only", file=sys.stderr)
            return 2
        env["SKIP_SUPABASE_SYNC"] = "1"
    elif not env_path.exists():
        print("Нет .env.supabase.local (или укажите --snapshot-only)", file=sys.stderr)
        return 2
    else:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

    cred = env.get("GOOGLE_SERVICE_ACCOUNT_JSON") or str(ROOT / "google-service-account.json")
    if Path(cred).exists():
        env["GOOGLE_SERVICE_ACCOUNT_JSON"] = cred

    filter_cmd = [sys.executable, str(ROOT / "scripts" / "apply_all_filters_from_sheet.py")]
    if snapshot_only:
        filter_cmd.append("--snapshot-only")

    rebuild_script = (
        ROOT / "scripts" / "rebuild_from_catalog_snapshot.py"
        if snapshot_only or SNAPSHOT_PATH.exists()
        else ROOT / "scripts" / "rebuild_from_supabase.py"
    )

    cmds: list[list[str]] = [
        [sys.executable, str(ROOT / "scripts" / "backfill_missing_from_sheet_links.py")],
    ]
    if not args.skip_filters:
        cmds.append(filter_cmd)
    if not args.skip_rebuild:
        cmds.append([sys.executable, str(rebuild_script)])
    if not args.skip_verify:
        cmds.append([sys.executable, str(ROOT / "tools" / "verify_object_media.py")])
    if snapshot_only:
        cmds.append([sys.executable, str(ROOT / "tools" / "validate_catalog_snapshot.py")])

    for cmd in cmds:
        print("+", " ".join(cmd), flush=True)
        rc = subprocess.run(cmd, cwd=str(ROOT), env=env, check=False).returncode
        if rc != 0:
            print(f"Ошибка ({rc}): {' '.join(cmd)}", file=sys.stderr)
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
