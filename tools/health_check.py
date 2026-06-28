#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CheckResult:
    name: str
    status: str
    details: str
    return_code: int = 0


def run_command(name: str, cmd: list[str], *, timeout: int, env: dict[str, str] | None = None) -> CheckResult:
    try:
        completed = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(name, "ОШИБКА", f"таймаут {timeout} сек", 124)
    except FileNotFoundError as error:
        return CheckResult(name, "ОШИБКА", str(error), 127)

    output = (completed.stdout or "").strip()
    status = "OK" if completed.returncode == 0 else "ОШИБКА"
    return CheckResult(name, status, output[-1200:] if output else "без вывода", completed.returncode)


def validate_catalog_snapshot() -> CheckResult:
    script = ROOT / "tools" / "validate_catalog_snapshot.py"
    if script.exists():
        return run_command("Каталог", [sys.executable, str(script)], timeout=120)

    current_pages = ROOT / "output" / "current_pages.json"
    kv_cards = ROOT / "kvartira_cards.json"
    issues: list[str] = []
    hotel_count = 0
    kv_count = 0
    try:
        hotels = json.loads(current_pages.read_text(encoding="utf-8")) if current_pages.exists() else []
        kv = json.loads(kv_cards.read_text(encoding="utf-8")) if kv_cards.exists() else []
        hotel_count = len(hotels)
        kv_count = len(kv)
        for item in hotels:
            slug = str(item.get("slug") or "")
            if slug and not (ROOT / "hotels" / slug / "index.html").exists():
                issues.append(f"нет файла отеля: {slug}")
        for item in kv:
            slug = str(item.get("slug") or "")
            if slug and not (ROOT / "kvartira" / slug / "index.html").exists():
                issues.append(f"нет файла квартиры: {slug}")
    except Exception as error:  # noqa: BLE001
        return CheckResult("Каталог", "ОШИБКА", str(error), 1)

    if issues:
        return CheckResult("Каталог", "ОШИБКА", "\n".join(issues[:20]), 1)
    return CheckResult(
        "Каталог",
        "OK",
        f"валиден: отелей {hotel_count}, квартир {kv_count}, отсутствующих файлов 0",
    )


def launchd_status() -> CheckResult:
    labels = ("ru.abhazbereg.site-update-bot", "ru.abhazbereg.autosync")
    completed = subprocess.run(
        ["launchctl", "list"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = completed.stdout or ""
    lines = []
    for label in labels:
        matching = [line.strip() for line in output.splitlines() if label in line]
        if matching:
            lines.append(f"{label}: запущен ({matching[0]})")
        else:
            lines.append(f"{label}: не найден в launchd")
    status = "OK" if any("site-update-bot: запущен" in line for line in lines) else "ВНИМАНИЕ"
    return CheckResult("launchd-бот", status, "\n".join(lines), completed.returncode)


def python_status() -> CheckResult:
    version = sys.version_info
    status = "OK" if version >= (3, 10) else "ВНИМАНИЕ"
    details = (
        f"текущий Python: {sys.version.split()[0]}; "
        + ("версия подходит" if status == "OK" else "лучше перейти на Python 3.10+ / 3.11")
    )
    return CheckResult("Python", status, details)


def check_key_pages() -> CheckResult:
    candidates = [
        ROOT / "index.html",
        ROOT / "karta" / "index.html",
    ]
    candidates.extend(sorted((ROOT / "hotels").glob("*/index.html"))[:3])
    candidates.extend(sorted((ROOT / "kvartira").glob("*/index.html"))[:3])
    podborki = ROOT / "podborki"
    if podborki.exists():
        candidates.extend(sorted(podborki.glob("*/index.html"))[:2])

    issues: list[str] = []
    checked = 0
    for path in candidates:
        if not path.exists():
            issues.append(f"нет файла: {path.relative_to(ROOT)}")
            continue
        checked += 1
        html_text = path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html_text, "html.parser")
        is_object_page = "hotels" in path.parts or "kvartira" in path.parts
        if is_object_page and not soup.select_one("main"):
            issues.append(f"{path.relative_to(ROOT)}: нет main")
        if not is_object_page and not soup.select_one("body"):
            issues.append(f"{path.relative_to(ROOT)}: нет body")
        if is_object_page:
            media_urls = [
                tag.get("src") or tag.get("data-src")
                for tag in soup.select("main img, main video, main source")
                if tag.get("src") or tag.get("data-src")
            ]
            if not media_urls:
                issues.append(f"{path.relative_to(ROOT)}: не найдено медиа в main")
            if "gallery" not in html_text and "hotel-media" not in html_text:
                issues.append(f"{path.relative_to(ROOT)}: не видны признаки галереи")

    if issues:
        return CheckResult("Ключевые страницы", "ОШИБКА", "\n".join(issues[:20]), 1)
    return CheckResult("Ключевые страницы", "OK", f"проверено страниц: {checked}")


def check_review_blocks() -> CheckResult:
    slugs = [
        "parus-vidovoy-otel-s-basseynom-i-stolovoy-2602",
        "apsa-park-otel-v-zapovednike-2611",
        "pegas-otel-na-pervoy-linii-vid-na-more-2574",
        "mulberri-otel-na-plyazhe-s-basseynom-i-kafe-3074",
    ]
    forbidden = (
        "₽",
        "руб",
        "+7",
        "whatsapp",
        "t.me",
        "подпись из telegram",
        "из комментариев telegram",
        "служеб",
        "брон",
    )
    issues: list[str] = []
    checked_cards = 0
    for slug in slugs:
        path = ROOT / "hotels" / slug / "index.html"
        if not path.exists():
            issues.append(f"{slug}: нет страницы")
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
        section = soup.select_one("#supplemental-comments")
        if not section:
            issues.append(f"{slug}: нет блока дополнительных обзоров")
            continue
        cards = section.select(".room-overview-card")
        if not cards:
            issues.append(f"{slug}: блок дополнительных обзоров пустой")
            continue
        checked_cards += len(cards)
        if not section.select(".comment-media-grid img, .comment-media-grid video"):
            issues.append(f"{slug}: в блоке обзоров нет фото или видео")
        text = section.get_text(" ", strip=True).lower()
        found = [word for word in forbidden if word in text]
        if found:
            issues.append(f"{slug}: в обзорах найдены запрещённые фразы/контакты: {', '.join(found)}")
    if issues:
        return CheckResult("Свежие обзоры", "ОШИБКА", "\n".join(issues), 1)
    return CheckResult("Свежие обзоры", "OK", f"проверено карточек: {checked_cards}")


def write_report(results: list[CheckResult], path: Path) -> None:
    lines = ["Health-check сайта и бота", ""]
    for result in results:
        lines.append(f"[{result.status}] {result.name}")
        lines.append(result.details)
        lines.append("")
    bad = [r for r in results if r.status == "ОШИБКА"]
    warn = [r for r in results if r.status == "ВНИМАНИЕ"]
    if bad:
        lines.append(f"Итог: есть технические проблемы ({len(bad)}).")
    elif warn:
        lines.append(f"Итог: критичных ошибок нет, есть предупреждения ({len(warn)}).")
    else:
        lines.append("Итог: всё выглядит штатно.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверить здоровье сайта, медиа и Telegram-бота.")
    parser.add_argument("--skip-telegram", action="store_true", help="Не проверять доступ к Telegram.")
    parser.add_argument("--report", default=str(ROOT / "output" / "health_check_report.txt"))
    args = parser.parse_args()

    env = os.environ.copy()
    env["TG_SCRIPT_TIMEOUT_SECONDS"] = env.get("TG_SCRIPT_TIMEOUT_SECONDS", "180")
    env["TG_CONNECT_TIMEOUT_SECONDS"] = env.get("TG_CONNECT_TIMEOUT_SECONDS", "30")

    results = [
        validate_catalog_snapshot(),
        run_command(
            "Медиа-ссылки",
            [sys.executable, str(ROOT / "tools" / "verify_object_media.py")],
            timeout=120,
        ),
        run_command(
            "Карта объектов",
            [sys.executable, str(ROOT / "scripts" / "sync_objects_map_points.py"), "--no-write"],
            timeout=180,
        ),
        check_key_pages(),
        check_review_blocks(),
    ]
    if args.skip_telegram:
        results.append(CheckResult("Telegram watch", "ПРОПУЩЕНО", "проверка пропущена флагом --skip-telegram"))
    else:
        results.append(
            run_command(
                "Telegram watch",
                [sys.executable, str(ROOT / "scripts" / "watch_telegram_updates.py"), "--no-write-state", "--limit", "3"],
                timeout=210,
                env=env,
            )
        )
    results.extend([launchd_status(), python_status()])

    report_path = Path(args.report)
    write_report(results, report_path)
    print(report_path)
    for result in results:
        print(f"[{result.status}] {result.name}")
    return 1 if any(r.status == "ОШИБКА" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
