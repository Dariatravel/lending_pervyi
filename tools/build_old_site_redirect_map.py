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

# Адреса из выгрузки Яндекс.Вебмастера «Страницы в поиске» (16.08.2026),
# которых нет в sitemap Тильды: статьи старого блога (/tpost/) и три
# карточки. Подобраны вручную, у каждой статьи есть точная пара в новом блоге.
EXTRA_MAP = {
    "/tpost/1zusms4cv1-chego-boyatsya-v-abhazii": "/blog/chego-boyatsya-v-abhazii/",
    "/tpost/24cc5d0vg1-chto-vazhno-znat-pro-svyaz-v-abhazii": "/blog/mobilnaya-svyaz-i-internet-abkhaziya/",
    "/tpost/29xaf86hv1-vazhnie-pravila-poezdki-v-abhaziyu-s-det": "/blog/pravila-poezdki-s-detmi-abkhaziya-2026/",
    "/tpost/3zgj3ahdx1-pamyatka-turistu-v-abhaziyu-2026": "/blog/pamyatka-turistu-abkhazia/",
    "/tpost/9fdztv8lv1-vezd-v-abhaziyu-dlya-kakih-stran-deistvu": "/blog/inostrannye-pravila-vezda-abkhazia/",
    "/tpost/anz10dnpj1-v-abhaziyu-s-zhivotnimi-chto-nuzhno-znat": "/blog/poezdka-v-abhaziyu-s-zhivotnym/",
    "/tpost/dfbup2mky1-goryachie-istochniki-v-abhazii": "/blog/goryachie-istochniki-abhazii/",
    "/tpost/fxrrv8czr1-abhaziya-minusi-otdiha": "/blog/minusy-otdyha-abkhazia/",
    "/tpost/granica": "/blog/kak-projti-granicu-psou/",
    "/tpost/jckj0uma31-za-eto-vas-lishat-prav-v-abhazii": "/blog/prava-i-shtrafy-avto-abhaziya/",
    "/tpost/kurort": "/blog/kak-vybrat-kurort-abkhaziya-pervyy-raz/",
    "/tpost/presentation": "/blog/znakomstvo-darya-bronirovanie-abhaziya/",
    "/tpost/smfja6upd1-edinii-bilet-v-abhaziyu-chto-eto-takoe-i": "/blog/edinyj-bilet-v-abhaziyu/",
    "/tpost/uedtmffth1-sobralis-v-abhaziyu-proverte-dolgi-do-po": "/blog/proverka-dolgov-pered-poezdkoj/",
    "/tproduct/264171370802-nora-gostevoi-dom-ekonom": "/hotels/nora-gostevoy-dom-3851/",
    "/tproduct/678683261522-afina-kvartira-2-k": "/kvartira/afina-kvartira-2k-1488/",
    # «ГРЕЙ ХАУС» эко-отель — на новом сайте объекта нет (подтвердить у Дарьи)
    "/catalogcity/tproduct/259792702692-grei-haus-eko-otel-s-basseinom-": "/",
}
STATIC_MAP.update(EXTRA_MAP)


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
            if brand and cand["brand"]:
                # Сравниваем ТОЛЬКО имя в кавычках: полные названия совпадают
                # по словам «квартира 2-к» и женят тёзок («СЕМЕЙНАЯ» → «СОЛНЕЧНАЯ»).
                score = SequenceMatcher(None, brand, cand["brand"]).ratio()
                tokens_old, tokens_new = set(brand.split()), set(cand["brand"].split())
                # «ЛЮБОВЬ» и «ВИЛЛА ЛЮБОВЬ» — один объект: имя вложено в имя
                if tokens_old and tokens_new and (tokens_old <= tokens_new or tokens_new <= tokens_old):
                    score = max(score, 0.9)
            else:
                score = SequenceMatcher(None, norm(old_title), cand["norm"]).ratio()
            if score > best_score:
                best, best_score = cand, score
        if best and best_score >= 0.75:
            redirects[old_path] = {"to": best["path"], "old_title": old_title,
                                   "new_title": best["title"], "score": round(best_score, 2)}
            matched.append((old_path, old_title, best["title"], round(best_score, 2)))
        else:
            hint = f"похоже на {best['title']} ({round(best_score, 2)})" if best else "—"
            redirects[old_path] = {"to": "/", "old_title": old_title, "new_title": "",
                                   "score": round(best_score, 2), "note": hint}
            unmatched.append((old_path, old_title, hint))

    payload = {}
    for old_path, value in redirects.items():
        payload[old_path] = value if isinstance(value, dict) else {"to": value, "old_title": "", "new_title": ""}
    OUT_PATH.write_text(json.dumps({"origin": "https://abhazbereg.ru",
                                    "target": "https://абхазберег.рф",
                                    "redirects": dict(sorted(payload.items()))},
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
