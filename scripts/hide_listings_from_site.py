#!/usr/bin/env python3
"""Скрыть объекты с сайта: tools/hidden_listings.json → is_active=false → rebuild каталога и подборок."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from listing_visibility import deactivate_slugs, load_hidden_slugs, merge_hidden_slugs, use_snapshot_store  # noqa: E402
from sync_catalog_from_telegram import ENV_FILE, SupabaseClient, load_env  # noqa: E402

REPORT = ROOT / "output" / "hidden_listings_report.txt"


def main() -> int:
    extra = [a for a in sys.argv[1:] if not a.startswith("-")]
    if extra:
        merge_hidden_slugs(extra)

    slugs = load_hidden_slugs()
    if not slugs:
        print("Нет slug в tools/hidden_listings.json", file=sys.stderr)
        return 1

    supa: SupabaseClient | None = None
    if not use_snapshot_store():
        env = load_env(ENV_FILE)
        supa = SupabaseClient(url=env["SUPABASE_URL"].rstrip("/"), service_key=env["SUPABASE_SERVICE_ROLE_KEY"])
    done, missing = deactivate_slugs(supa, slugs)

    rebuild = (
        ROOT / "scripts" / "rebuild_from_catalog_snapshot.py"
        if use_snapshot_store()
        else ROOT / "scripts" / "rebuild_from_supabase.py"
    )
    for cmd in (
        [sys.executable, str(rebuild)],
        [sys.executable, str(ROOT / "scripts" / "build_podborki_from_filters.py")],
    ):
        print("+", " ".join(cmd), flush=True)
        rc = subprocess.run(cmd, cwd=str(ROOT), check=False).returncode
        if rc != 0:
            print(f"Ошибка ({rc}): {' '.join(cmd)}", file=sys.stderr)
            return rc

    store = "catalog snapshot" if use_snapshot_store() else "Supabase"
    lines = [
        "Скрытые объекты (is_active=false, убраны из каталога и подборок)",
        "",
        f"Всего в hidden_listings.json: {len(slugs)}",
        f"Деактивировано в {store}: {len(done)}",
        "",
        "Скрыты:",
        *[f"- {s}" for s in done],
    ]
    if missing:
        lines.extend(["", f"Не найдены в {store}:", *[f"- {s}" for s in missing]])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
