#!/usr/bin/env python3
"""Вернуть объекты на сайт: убрать из hidden_listings.json → is_active=true → rebuild каталога."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from listing_visibility import activate_slugs, load_hidden_slugs, save_hidden_slugs  # noqa: E402
from sync_catalog_from_telegram import ENV_FILE, SupabaseClient, load_env  # noqa: E402

REPORT = ROOT / "output" / "shown_listings_report.txt"


def main() -> int:
    extra = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not extra:
        print("Укажите slug через пробел или --from-hidden", file=sys.stderr)
        return 1

    if extra == ["--from-hidden"]:
        slugs = load_hidden_slugs()
    else:
        slugs = {s.strip() for s in extra if s.strip()}

    if not slugs:
        print("Нет slug для активации", file=sys.stderr)
        return 1

    remaining = load_hidden_slugs() - slugs
    save_hidden_slugs(remaining)

    env = load_env(ENV_FILE)
    supa = SupabaseClient(url=env["SUPABASE_URL"].rstrip("/"), service_key=env["SUPABASE_SERVICE_ROLE_KEY"])
    done, missing = activate_slugs(supa, slugs)

    for cmd in (
        [sys.executable, str(ROOT / "scripts" / "rebuild_from_supabase.py")],
        [sys.executable, str(ROOT / "scripts" / "build_objects_map_points.py")],
        [sys.executable, str(ROOT / "scripts" / "build_podborki_from_filters.py")],
    ):
        print("+", " ".join(cmd), flush=True)
        rc = subprocess.run(cmd, cwd=str(ROOT), check=False).returncode
        if rc != 0:
            print(f"Ошибка ({rc}): {' '.join(cmd)}", file=sys.stderr)
            return rc

    lines = [
        "Показанные объекты (is_active=true, добавлены в каталог)",
        "",
        f"Активировано в Supabase: {len(done)}",
        f"Убрано из hidden_listings.json: {len(slugs & (load_hidden_slugs() | slugs))}",
        "",
        "Активны:",
        *[f"- {s}" for s in done],
    ]
    if missing:
        lines.extend(["", "Не найдены в Supabase:", *[f"- {s}" for s in missing]])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
