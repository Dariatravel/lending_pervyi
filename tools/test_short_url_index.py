#!/usr/bin/env python3
"""Короткие ссылки объектов в data/catalog-index.json (Дарья 19.10.2026).

Каждому объекту — short_url вида https://abhazbereg.com/<ключ>: ручной ключ
(short-links.json) главнее автоматического, домен — латиницей.
Запуск: python3 tools/test_short_url_index.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog_snapshot import apply_short_urls, listing_path, short_key_by_path  # noqa: E402


def test_manual_beats_generated() -> None:
    keys = short_key_by_path(
        manual={"villa-leona": "/hotels/villa-leona-otel-2755/", "pamyatka": "/blog/pamyatka/"},
        generated={"villa": "/hotels/villa-leona-otel-2755/", "grass": "/hotels/grass-gostevoy-dom-3001/"},
    )
    assert keys["/hotels/villa-leona-otel-2755/"] == "villa-leona", keys
    assert keys["/hotels/grass-gostevoy-dom-3001/"] == "grass", keys


def test_shortest_key_within_same_kind() -> None:
    keys = short_key_by_path(manual={}, generated={"more-more": "/hotels/more-1/", "more": "hotels/more-1"})
    assert keys["/hotels/more-1/"] == "more", keys


def test_apply_short_urls_latin_domain_and_kvartira() -> None:
    items = [
        {"source_kind": "hotel", "slug": "grass-gostevoy-dom-3001"},
        {"source_kind": "kvartira", "slug": "biryuza-etazh-1367"},
        {"source_kind": "hotel", "slug": "bez-klyucha-1", "short_url": "https://abhazbereg.com/old"},
    ]
    keys = {"/hotels/grass-gostevoy-dom-3001/": "grass", "/kvartira/biryuza-etazh-1367/": "biryuza"}
    assert apply_short_urls(items, keys) == 2
    assert items[0]["short_url"] == "https://abhazbereg.com/grass"
    assert items[1]["short_url"] == "https://abhazbereg.com/biryuza"
    assert "short_url" not in items[2], "снятый ключ не должен оставаться в индексе"
    assert listing_path(items[1]) == "/kvartira/biryuza-etazh-1367/"


def test_real_registry_covers_catalog() -> None:
    import json

    index = json.loads((ROOT / "data" / "catalog-index.json").read_text(encoding="utf-8"))
    keys = short_key_by_path()
    items = [dict(row) for row in index["listings"]]
    found = apply_short_urls(items, keys)
    assert found == len(items), f"без короткой ссылки: {[r['slug'] for r in items if 'short_url' not in r][:10]}"
    leona = [r for r in items if r["slug"].startswith("villa-leona-otel")]
    if leona:
        assert leona[0]["short_url"] == "https://abhazbereg.com/villa-leona", leona[0]["short_url"]


def main() -> int:
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"Все проверки пройдены: {len(tests)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
