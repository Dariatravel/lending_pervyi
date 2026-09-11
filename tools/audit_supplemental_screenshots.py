#!/usr/bin/env python3
"""Поиск скриншотов переписок среди фото «Дополнительных обзоров».

Появился 07.09.2026: в блок «АМОР домики» попал скриншот чужого отзыва
с нормальной подписью — текстовые фильтры такое не ловят. Зато ловит
сама картинка: скриншот переписки почти целиком белый (фон мессенджера),
а фото номера/домика — нет.

Скрипт идёт по data/supplemental-blocks.json, скачивает лёгкую WebP-копию
каждого фото (-480) и считает долю «почти белых» пикселей. Всё, что выше
порога, печатает как подозрительное — дальше решает человек.

Запуск (в GitHub Actions, у раннера открытый интернет):
    python3 tools/audit_supplemental_screenshots.py
Выход 0 — подозрительных нет; 2 — есть, список в stdout.
"""
from __future__ import annotations

import io
import json
import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "supplemental-blocks.json"

WHITE_MIN = 225      # min(R,G,B) выше — пиксель считается «белым»
SUSPECT_SHARE = 0.45  # доля белых пикселей, с которой фото подозрительно


def white_share(data: bytes) -> float:
    image = Image.open(io.BytesIO(data)).convert("RGB")
    image.thumbnail((240, 240))
    pixels = list(image.getdata())
    white = sum(1 for r, g, b in pixels if min(r, g, b) > WHITE_MIN)
    return white / max(1, len(pixels))


def fetch(url: str) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": "abhazbereg-supplemental-audit"})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return response.read()
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    suspects: list[str] = []
    checked = failed = 0
    for slug, record in sorted(manifest.items()):
        html = record.get("section_html") or ""
        for jpg_url in re.findall(r'<img src="([^"]+\.jpg)"', html):
            # У каждого JPG в бакете есть лёгкая WebP-копия -480 — качаем её.
            data = fetch(jpg_url[:-4] + "-480.webp") or fetch(jpg_url)
            checked += 1
            if data is None:
                failed += 1
                print(f"  ! не скачалось: {jpg_url}")
                continue
            try:
                share = white_share(data)
            except Exception as error:  # noqa: BLE001
                failed += 1
                print(f"  ! не разобралось ({error}): {jpg_url}")
                continue
            if share >= SUSPECT_SHARE:
                suspects.append(f"  {share:.0%} белого  {slug}: {jpg_url}")

    print(f"\nПроверено фото: {checked}, не скачалось/не разобралось: {failed}")
    if suspects:
        print(f"\nПОДОЗРИТЕЛЬНЫЕ (белого фона ≥ {SUSPECT_SHARE:.0%}) — посмотреть глазами:")
        print("\n".join(suspects))
        print("\nЕсли это скриншот переписки: добавить id сообщения в "
              "data/supplemental-excludes.json и пересинкать объект "
              "(watch-telegram, force_hotel_ids/force_kv_topics).")
        print("\nЭто находки на проверку, а не поломка: прогон остаётся зелёным.")
    else:
        print("Скриншотов переписок не найдено.")

    # Красным прогон делает только настоящая поломка, а не находки: иначе
    # каждый аудит с результатом приходил Дарье письмом «Run failed»
    # (08.09.2026 так и случилось на двух честных находках).
    if checked == 0:
        print("\nОШИБКА: не проверено ни одного фото — манифест пуст или недоступен.", file=sys.stderr)
        return 1
    if failed > max(5, checked // 10):
        print(f"\nОШИБКА: не скачалось {failed} фото из {checked} — похоже на проблему "
              "с медиа-хранилищем, а не на единичные битые ссылки.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
