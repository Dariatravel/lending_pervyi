#!/usr/bin/env python3
"""Build minified CSS/JS assets for the static site."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_js_minifier(source: str, outfile: str) -> None:
    subprocess.run(
        [
            "npx",
            "--yes",
            "terser",
            source,
            "--compress",
            "--mangle",
            "--output",
            outfile,
        ],
        cwd=ROOT,
        check=True,
    )


def run_css_minifier(source: str, outfile: str) -> None:
    subprocess.run(
        [
            "npx",
            "--yes",
            "esbuild",
            source,
            "--minify",
            "--target=es2018",
            f"--outfile={outfile}",
        ],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    run_js_minifier("scripts.js", "scripts.min.js")
    run_css_minifier("styles.css", "styles.min.css")
    for filename in ("scripts.min.js", "styles.min.css"):
        path = ROOT / filename
        print(f"{filename}: {path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
