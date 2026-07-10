#!/usr/bin/env python3
"""Fail if media/ paths are tracked in git (Yandex Object Storage is the source of truth)."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files", "media"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "git ls-files failed", file=sys.stderr)
        return 2

    tracked = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not tracked:
        print("OK: media/ is not tracked in git")
        return 0

    print(f"FAIL: {len(tracked)} file(s) under media/ are still tracked in git")
    for line in tracked[:25]:
        print(f"  {line}")
    if len(tracked) > 25:
        print(f"  ... and {len(tracked) - 25} more")
    print("Fix: git rm -r --cached media/  (local files stay on disk)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
