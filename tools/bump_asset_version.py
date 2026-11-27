#!/usr/bin/env python3
"""Bump static asset version across generated HTML, service worker and JS."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "data" / "asset-version.txt"
VERSION_RE = re.compile(r"\?v=\d{10,14}")
ASSET_VERSION_RE = re.compile(r'(const\s+ASSET_VERSION\s*=\s*")[^"]+(")')
CACHE_VERSION_RE = re.compile(r"(abhazbereg-[a-z-]+-v)\d{10,14}")


def iter_text_files() -> list[Path]:
    paths = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "*.html", "*.js", "*.py"],
        cwd=ROOT,
    ).decode().split("\0")
    excluded = {"media", "output", "node_modules", ".venv", ".venv-banner"}
    return sorted(
        ROOT / name for name in paths
        if name and not excluded.intersection(Path(name).parts) and (ROOT / name).is_file()
    )


def replace_version(path: Path, version: str) -> bool:
    text = path.read_text(encoding="utf-8")
    updated = VERSION_RE.sub(f"?v={version}", text)
    if path.name == "scripts.js":
        updated = ASSET_VERSION_RE.sub(rf"\g<1>{version}\2", updated)
    if path.name == "sw.js":
        updated = CACHE_VERSION_RE.sub(rf"\g<1>{version}", updated)
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", nargs="?", help="Версия вида YYYYMMDDHHMM. По умолчанию текущее время.")
    parser.add_argument("--skip-minify", action="store_true")
    args = parser.parse_args()

    version = args.version or datetime.now().strftime("%Y%m%d%H%M")
    if not re.fullmatch(r"\d{10,14}", version):
        print("Версия должна состоять из 10-14 цифр.", file=sys.stderr)
        return 2

    VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(version + "\n", encoding="utf-8")

    changed = sum(1 for path in iter_text_files() if replace_version(path, version))
    if not args.skip_minify:
        subprocess.run([sys.executable, str(ROOT / "tools" / "minify_assets.py")], cwd=ROOT, check=True)

    print(f"asset_version={version} changed_files={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
