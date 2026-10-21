#!/usr/bin/env python3
"""Фильтры из таблицы «БАЗА», вкладка СОЦСЕТИ: питание и пляж не выдумываются.

Пустая ячейка — «не указано» ([]), а не «Без питания» и не «Галечный»
(21.10.2026). Явно указанные значения сохраняются как раньше.
Запуск: python3 tools/test_sheet_filters_inference.py
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import apply_all_filters_from_sheet as aaf  # noqa: E402
from apply_all_filters_from_sheet import COL, infer_all_filters, infer_beach, infer_food  # noqa: E402


def row(**cells: str) -> list[str]:
    out = [""] * (max(COL.values()) + 1)
    for key, value in cells.items():
        out[COL[key]] = value
    return out


def check(ok: bool, name: str, failures: list[str]) -> None:
    if not ok:
        failures.append(name)


FOOD = [
    # (AV, ожидаемо, что проверяем)
    ("", [], "пусто → не указано"),
    ("   ", [], "одни пробелы → не указано"),
    ("по договорённости", [], "текст не разобран → не указано"),
    ("n/a", [], "n/a → не указано"),
    ("?", [], "вопрос → не указано"),
    ("Своя кухня", ["no-food"], "своя кухня → без питания"),
    ("самостоятельно", ["no-food"], "готовят сами → без питания"),
    ("Завтраки, есть кухня", ["breakfast"], "завтраки и кухня → только завтраки"),
    ("Питания нет", ["no-food"], "питания нет"),
    ("питание не предусмотрено", ["no-food"], "питание не предусмотрено"),
    ("Отсутствует", ["no-food"], "отсутствует"),
    ("Нет.", ["no-food"], "«Нет.» с точкой"),
    ("–", ["no-food"], "короткое тире"),
    ("нет питания, рядом кафе", ["no-food", "cafe"], "нет питания и кафе — кафе не теряется"),
    ("Без питания", ["no-food"], "явно «без питания»"),
    ("без питания, рядом кафе", ["no-food", "cafe"], "без питания и кафе"),
    ("нет", ["no-food"], "отрицание «нет»"),
    ("Нет", ["no-food"], "отрицание «Нет»"),
    ("—", ["no-food"], "прочерк"),
    ("не предусмотрено", ["no-food"], "не предусмотрено"),
    ("Завтраки", ["breakfast"], "завтраки"),
    ("Завтрак, обед, ужин", ["full-board"], "трёхразовое"),
    ("Полупансион", ["half-board"], "полупансион"),
    ("Кафе на территории", ["cafe"], "кафе"),
    ("Столовая", ["cafe"], "столовая"),
]

BEACH = [
    # (AD сосновый, AE песчаный Лдзаа, AF песчаный Сухум, ожидаемо, что проверяем)
    ("", "", "", [], "все пусто → не указано (раньше pebble)"),
    ("нет", "", "", [], "одно «нет», остальные пусто → не указано"),
    ("нет", "нет", "", [], "два «нет», одно пусто → не указано"),
    ("нет", "нет", "нет", ["pebble"], "все три «нет» → галечный"),
    ("Нет", "—", "0", ["pebble"], "все три отрицания разными словами → галечный"),
    ("да", "", "", ["pine-pebble-ldzaa-pitsunda"], "сосновый"),
    ("да", "нет", "нет", ["pine-pebble-ldzaa-pitsunda"], "сосновый, остальные «нет» — без галечного"),
    ("", "Лдзаа (песок)", "", ["sand-ldzaa"], "песок Лдзаа"),
    ("", "песок/мелкая галька", "", ["pitsunda-bay-mixed"], "Пицундская бухта"),
    ("", "", "да", ["sand-sukhum"], "песок Сухум"),
    ("да", "", "да", ["pine-pebble-ldzaa-pitsunda", "sand-sukhum"], "два пляжа сразу"),
    # Как было: «да» без слова «песок» в AE кода не даёт, но и галечным не делает.
    ("", "да", "", [], "AE «да» без уточнения → не указано"),
]


def check_dry_run(failures: list[str]) -> None:
    """--dry-run: ничего не пишет и показывает, что «без питания»/«галечный» ушли бы в «не указано»."""
    listing = {
        "slug": "test-1",
        "source_channel": "abhazbooking",
        "source_message_id": 1,
        "source_kind": "hotel",
        "is_active": True,
        "details": {"filters": {"food": ["no-food"], "beach": ["pebble"]}},
    }
    sheet = [row(title="Тест", tg_link="https://t.me/abhazbooking/1")]
    writes: list[str] = []
    saved = {name: getattr(aaf, name) for name in (
        "pick_google_credentials_path", "fetch_sheet_rows", "snapshot_load_listings",
        "snapshot_update_filters", "patch_listing_details", "listing_exists_on_site", "REPORT_PATH",
    )}
    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "report.txt"
        try:
            aaf.pick_google_credentials_path = lambda: Path(tmp)
            aaf.fetch_sheet_rows = lambda _path: sheet
            aaf.snapshot_load_listings = lambda: [listing]
            aaf.snapshot_update_filters = lambda slug, _f: writes.append(f"snapshot {slug}") or True
            aaf.patch_listing_details = lambda *_a: writes.append("supabase")
            aaf.listing_exists_on_site = lambda *_a: True
            aaf.REPORT_PATH = report_path
            out = io.StringIO()
            old_argv = sys.argv
            sys.argv = ["apply_all_filters_from_sheet.py", "--dry-run"]
            try:
                with contextlib.redirect_stdout(out):
                    aaf.main()
            finally:
                sys.argv = old_argv
        finally:
            for name, value in saved.items():
                setattr(aaf, name, value)
        text = out.getvalue()
        check(writes == [], f"сухой прогон: ничего не пишет, а записал {writes}", failures)
        check(not report_path.exists(), "сухой прогон: файл отчёта не создан", failures)
        check("Сухой прогон: ничего не записано" in text, "сухой прогон: строка в отчёте", failures)
        check("food: no-food → не указано: 1" in text, f"сухой прогон: питание было → стало\n{text}", failures)
        check("beach: pebble → не указано: 1" in text, "сухой прогон: пляж было → стало", failures)
        check("Питание не указано (AV пусто): 1" in text, "сухой прогон: счёт пустого питания", failures)


def check_normal_run_writes(failures: list[str]) -> None:
    """Без --dry-run запись в snapshot идёт, как раньше."""
    listing = {
        "slug": "test-1", "source_channel": "abhazbooking", "source_message_id": 1,
        "source_kind": "hotel", "is_active": True,
        "details": {"filters": {"food": ["no-food"], "beach": ["pebble"]}},
    }
    sheet = [row(title="Тест", tg_link="https://t.me/abhazbooking/1", food_filter="Завтраки")]
    writes: list[tuple[str, list[str]]] = []
    names = ("pick_google_credentials_path", "fetch_sheet_rows", "snapshot_load_listings",
             "snapshot_update_filters", "listing_exists_on_site", "REPORT_PATH")
    saved = {name: getattr(aaf, name) for name in names}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            aaf.pick_google_credentials_path = lambda: Path(tmp)
            aaf.fetch_sheet_rows = lambda _path: sheet
            aaf.snapshot_load_listings = lambda: [listing]
            aaf.snapshot_update_filters = lambda slug, f: writes.append((slug, list(f["food"]))) or True
            aaf.listing_exists_on_site = lambda *_a: True
            aaf.REPORT_PATH = Path(tmp) / "report.txt"
            old_argv = sys.argv
            sys.argv = ["apply_all_filters_from_sheet.py", "--snapshot-only"]
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    aaf.main()
            finally:
                sys.argv = old_argv
            check(aaf.REPORT_PATH.exists(), "обычный прогон: файл отчёта записан", failures)
        finally:
            for name, value in saved.items():
                setattr(aaf, name, value)
    check(writes == [("test-1", ["breakfast"])], f"обычный прогон: запись в snapshot {writes}", failures)


def main() -> int:
    failures: list[str] = []

    for text, expected, name in FOOD:
        got = infer_food(row(food_filter=text))
        check(got == expected, f"питание: {name}: {text!r} → {got}, ждали {expected}", failures)

    for ad, ae, af, expected, name in BEACH:
        got = infer_beach(row(beach_ad=ad, beach_ae=ae, beach_af=af))
        check(got == expected, f"пляж: {name}: {(ad, ae, af)} → {got}, ждали {expected}", failures)

    empty = infer_all_filters(row(title="Гостевой дом"))
    check(all(values == [] for values in empty.values()), f"пустая строка → все группы пусты: {empty}", failures)

    check_dry_run(failures)
    check_normal_run_writes(failures)

    if failures:
        print("ОШИБКИ:")
        for failure in failures:
            print(" -", failure)
        return 1
    print(f"OK: питание {len(FOOD)}, пляж {len(BEACH)}, пустая строка, сухой и обычный прогон")
    return 0


if __name__ == "__main__":
    sys.exit(main())
