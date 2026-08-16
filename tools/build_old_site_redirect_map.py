#!/usr/bin/env python3
"""Карта редиректов со старой Тильды (abhazbereg.ru) на абхазберег.рф.

Читает output/old-site-audit.json (собирает tools/audit_old_tilda_site.py),
сопоставляет карточки Тильды с объектами каталога по названию в кавычках
и пишет data/old-site-redirects.json: {старый путь: новый путь}.
Несопоставившиеся страницы ведут на главную и перечисляются в отчёте —
их надо показать Дарье глазами.
"""
from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "output" / "old-site-audit.json"
CATALOG_PATH = ROOT / "data" / "catalog-index.json"
OUT_PATH = ROOT / "data" / "old-site-redirects.json"
REPORT_PATH = ROOT / "output" / "old-site-redirect-report.txt"

# Страницы-разделы Тильды — посадка на разделы нового сайта.
STATIC_MAP = {
    "/": "/",
    "/catalog": "/",
    "/catalogcity": "/",
    "/page62959751.html": "/pitsunda/",   # «Пицунда, Лдзаа»
    "/page62959771.html": "/suhum/",      # «Сухум и Восточная Абхазия»
}


def norm(text: str) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[^а-яa-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def quoted_brand(title: str) -> str:
    match = re.search(r'[«"“„\']([^«»"“”„\']{2,60})[»"”“\']', title or "")
    return norm(match.group(1)) if match else ""


def main() -> int:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["listings"]

    candidates = []
    for listing in catalog:
        path = urlparse(str(listing.get("page_url") or "")).path
        title = str(listing.get("title") or "")
        candidates.append({
            "path": path,
            "title": title,
            "brand": quoted_brand(title),
            "norm": norm(title),
        })

    redirects: dict[str, str] = dict(STATIC_MAP)
    matched, unmatched = [], []

    for page in audit["pages"]:
        old_path = urlparse(page["url"]).path
        if old_path in redirects:
            continue
        old_title = page.get("h1") or page.get("title") or ""
        brand = quoted_brand(old_title)
        best, best_score = None, 0.0
        for cand in candidates:
            score = 0.0
            if brand and cand["brand"]:
                score = SequenceMatcher(None, brand, cand["brand"]).ratio()
            # полное название добавляет уверенности и разводит тёзок
            score = max(score, SequenceMatcher(None, norm(old_title), cand["norm"]).ratio())
            if score > best_score:
                best, best_score = cand, score
        if best and best_score >= 0.75:
            redirects[old_path] = best["path"]
            matched.append((old_path, old_title, best["title"], round(best_score, 2)))
        else:
            redirects[old_path] = "/"
            unmatched.append((old_path, old_title,
                              f"похоже на {best['title']} ({round(best_score, 2)})" if best else "—"))

    OUT_PATH.write_text(json.dumps({"origin": "https://abhazbereg.ru",
                                    "target": "https://абхазберег.рф",
                                    "redirects": dict(sorted(redirects.items()))},
                                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [f"Сопоставлено уверенно: {len(matched)}; на главную (нет пары): {len(unmatched)}", ""]
    lines.append("=== НЕ НАШЛИ ПАРУ (ведём на главную, показать Дарье) ===")
    for old_path, old_title, hint in sorted(unmatched):
        lines.append(f"  {old_path}")
        lines.append(f"      «{old_title[:80]}» | {hint}")
    lines.append("")
    lines.append("=== Сопоставленные (спорные внизу) ===")
    for old_path, old_title, new_title, score in sorted(matched, key=lambda m: -m[3]):
        lines.append(f"  {score:0.2f}  {old_path}")
        lines.append(f"        «{old_title[:70]}» → «{new_title[:70]}»")
    report = "\n".join(lines)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"\nКарта: {OUT_PATH.relative_to(ROOT)} ({len(redirects)} путей)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
