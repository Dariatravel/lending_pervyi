#!/usr/bin/env python3
"""Кнопка объекта должна копировать short_url из каталога, а не длинный путь."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "scripts.js").read_text(encoding="utf-8")
    assert 'fetch("/data/catalog-index.json"' in source
    assert 'row?.slug === slug && row?.source_kind === sourceKind' in source
    assert "btn.disabled = true;" in source
    assert "if (shortUrl) listingShareUrl = shortUrl;" in source
    assert "btn.disabled = false;" in source
    assert 'copyPublicUrl(btn, "Ссылка скопирована", "", listingShareUrl)' in source
    assert 'const url = explicitUrl || buildPublicShareUrl();' in source
    print("ok  кнопка объекта использует короткую ссылку и сохраняет резервный полный адрес")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
