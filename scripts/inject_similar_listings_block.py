#!/usr/bin/env python3
"""Вставляет блок похожих объектов в страницы отелей и квартир (если ещё нет)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BLOCK = """
      <section class="section hotel-site-concept__similar" data-similar-listings hidden>
        <div class="hotel-site-concept__similar-head">
          <p class="eyebrow">Похожие варианты</p>
          <h2>Может подойти, если смотрите рядом</h2>
          <p class="hotel-site-concept__similar-lead"></p>
        </div>
        <div class="catalog-grid hotel-site-concept__similar-grid" data-similar-listings-grid></div>
      </section>
"""

MARKER = "data-similar-listings"


def patch_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return False
    needle = "</main>"
    if needle not in text:
        return False
    path.write_text(text.replace(needle, f"{BLOCK}\n    {needle}", 1), encoding="utf-8")
    return True


def main() -> int:
    changed = 0
    for folder in ("hotels", "kvartira"):
        for path in sorted((ROOT / folder).glob("*/index.html")):
            if patch_file(path):
                changed += 1
    print(f"updated {changed} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
