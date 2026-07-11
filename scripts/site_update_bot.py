#!/usr/bin/env python3
"""Telegram bot for scheduled site update checks and automatic sync on VPS."""
from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import shlex
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

from telegram import ReplyKeyboardRemove, Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import Application, CommandHandler, ContextTypes

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env.site-update-bot"
STATE_PATH = ROOT / "output" / "site-update-bot-state.json"
LOG_DIR = ROOT / "output" / "site-update-bot"
WATCH_REPORT_PATH = ROOT / "output" / "telegram-watch-report.txt"
WATCH_TARGETS_PATH = ROOT / "output" / "telegram-watch-changed-targets.json"
MAP_REPORT_PATH = ROOT / "output" / "objects-map-sync-report.txt"
MAP_SUMMARY_PATH = ROOT / "output" / "objects-map-sync-summary.json"

STEP_LABELS = {
    "watch-telegram": "проверка новых правок в Telegram",
    "audit-parity": "сверка текстов сайта с Telegram",
    "audit-prices": "сверка цен",
    "verify-media": "проверка медиа",
    "check-map": "проверка точек карты",
    "update-map": "обновление точек карты",
    "new-from-sheet": "новые объекты из таблицы",
    "filters": "фильтры из таблицы",
    "rebuild": "пересборка сайта",
    "telegram-details": "обновление описаний",
    "telegram-prices": "обновление цен",
    "podborki": "пересборка подборок",
    "validate-snapshot": "проверка каталога",
    "apply_telegram_supplemental_comments": "добавление фото из комментариев",
    "accept-watch-state": "сохранение состояния проверки",
    "targeted-sync": "точечная синхронизация",
    "full-sync": "полная синхронизация",
    "git-status-before": "проверка git перед коммитом",
    "git-add": "подготовка файлов к коммиту",
    "git-commit": "коммит",
    "git-push": "публикация в GitHub",
    "git-status-after": "проверка git после коммита",
    "changed-targets": "поиск изменённых объектов",
    "sync_catalog_from_telegram": "синхронизация каталога из Telegram",
    "apply_all_filters_from_sheet": "фильтры из таблицы",
    "verify_object_media": "проверка медиа",
    "rebuild_from_catalog_snapshot": "пересборка сайта",
    "check_catalog_location_consistency": "проверка города объектов",
    "validate_catalog_snapshot": "проверка каталога",
}


@dataclass
class BotConfig:
    token: str
    allowed_chat_ids: set[int]
    interval_seconds: int
    initial_check_delay_seconds: int
    auto_apply: bool
    snapshot_only: bool
    command_timeout_seconds: int
    check_timeout_seconds: int


@dataclass
class CommandResult:
    name: str
    return_code: int
    log_path: Path


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def load_config() -> BotConfig:
    load_env_file(ENV_PATH)
    token = os.getenv("SITE_UPDATE_BOT_TOKEN", "").strip()
    raw_chat_ids = os.getenv("SITE_UPDATE_ALLOWED_CHAT_IDS", "").strip()
    allowed_chat_ids = {int(part.strip()) for part in raw_chat_ids.split(",") if part.strip()}
    if not token:
        raise RuntimeError("SITE_UPDATE_BOT_TOKEN is required")
    if not allowed_chat_ids:
        raise RuntimeError("SITE_UPDATE_ALLOWED_CHAT_IDS is required")

    return BotConfig(
        token=token,
        allowed_chat_ids=allowed_chat_ids,
        interval_seconds=int(os.getenv("SITE_UPDATE_CHECK_INTERVAL_SECONDS", "3600")),
        initial_check_delay_seconds=int(
            os.getenv(
                "SITE_UPDATE_INITIAL_CHECK_DELAY_SECONDS",
                os.getenv("SITE_UPDATE_CHECK_INTERVAL_SECONDS", "3600"),
            )
        ),
        auto_apply=bool_env("SITE_UPDATE_AUTO_APPLY", False),
        snapshot_only=bool_env("SITE_UPDATE_SNAPSHOT_ONLY", True),
        command_timeout_seconds=int(os.getenv("SITE_UPDATE_COMMAND_TIMEOUT_SECONDS", "21600")),
        check_timeout_seconds=int(os.getenv("SITE_UPDATE_CHECK_TIMEOUT_SECONDS", "1800")),
    )


CONFIG = load_config()
RUN_LOCK = asyncio.Lock()


def command_env() -> dict[str, str]:
    load_env_file(ROOT / ".env.supabase.local")
    load_env_file(ROOT / ".env.yandex.local")
    env = os.environ.copy()
    path_parts = [
        str(Path.home() / ".local" / "bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
        env.get("PATH", ""),
    ]
    env["PATH"] = ":".join(part for part in path_parts if part)
    if CONFIG.snapshot_only:
        env["SKIP_SUPABASE_SYNC"] = "1"
    env.setdefault("TG_SCRIPT_TIMEOUT_SECONDS", str(CONFIG.command_timeout_seconds))
    env.setdefault("TG_CONNECT_TIMEOUT_SECONDS", "120")
    google_creds = ROOT / "google-service-account.json"
    if google_creds.exists():
        env.setdefault("GOOGLE_SERVICE_ACCOUNT_JSON", str(google_creds))
    return env


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


async def run_command(name: str, command: list[str], *, timeout: int | None = None) -> CommandResult:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{timestamp()}-{name}.log"
    with log_path.open("w", encoding="utf-8") as log:
        log.write("+ " + " ".join(shlex.quote(part) for part in command) + "\n\n")
        log.flush()
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=ROOT,
            env=command_env(),
            stdout=log,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            return_code = await asyncio.wait_for(
                process.wait(),
                timeout=timeout or CONFIG.command_timeout_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            log.write("\n[timeout] process killed\n")
            return_code = 124
    return CommandResult(name=name, return_code=return_code, log_path=log_path)


def note_result(name: str, text: str, *, return_code: int = 0) -> CommandResult:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{timestamp()}-{name}.log"
    log_path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return CommandResult(name=name, return_code=return_code, log_path=log_path)


async def run_steps(steps: list[tuple[str, list[str]]], *, stop_on_error: bool = True) -> list[CommandResult]:
    results: list[CommandResult] = []
    for name, command in steps:
        result = await run_command(name, command)
        results.append(result)
        if stop_on_error and result.return_code != 0:
            break
    return results


def read_state() -> dict[str, object]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_state(state: dict[str, object]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def count_report_markers(path: Path, markers: tuple[str, ...]) -> int:
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8", errors="ignore")
    return sum(text.count(marker) for marker in markers)


def read_watch_report() -> str:
    if not WATCH_REPORT_PATH.exists():
        return "Telegram watch: отчёт ещё не создан."
    return WATCH_REPORT_PATH.read_text(encoding="utf-8", errors="ignore").strip()


AUTO_MODE_TEXT = (
    "Бот работает автоматически: каждый час проверяет Telegram и обновляет сайт.\n"
    "Сообщения приходят только когда изменения опубликованы или если возникла ошибка."
)


def format_changed_items(targets: dict[str, object], limit: int = 8) -> str:
    items = targets.get("items") or []
    if not isinstance(items, list) or not items:
        return ""
    lines = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("slug") or "объект")
        parts = ", ".join(str(part) for part in item.get("changed_parts") or [])
        old_id = item.get("reposted_from_message_id")
        if old_id and "перевыкладка" in parts:
            lines.append(f"- {title}: перевыкладка старого объекта, старый пост {old_id}")
        else:
            lines.append(f"- {title}: {parts}")
    if len(items) > limit:
        lines.append(f"- и ещё {len(items) - limit} объект(ов)")
    return "\n".join(lines)


def format_new_objects(targets: dict[str, object], limit: int = 8) -> str:
    items = targets.get("new_objects") or []
    if not isinstance(items, list) or not items:
        return ""
    lines = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "новый объект")
        channel = str(item.get("channel") or "").strip()
        message_id = str(item.get("message_id") or "").strip()
        topic_id = item.get("topic_id")
        url = str(item.get("telegram_url") or "").strip()
        topic_part = f", тема {topic_id}" if topic_id else ""
        source = f"{channel}/{message_id}{topic_part}".strip("/")
        suffix = f"; {url}" if url else ""
        lines.append(f"- {title}: {source}{suffix}")
    if len(items) > limit:
        lines.append(f"- и ещё {len(items) - limit} объект(ов)")
    return "\n".join(lines)


def summarize_check() -> str:
    media_report = ROOT / "output" / "hidden_listings_report.txt"
    media_note = "медиа-проверка выполнена" if media_report.exists() else "медиа-проверка без отчета"
    map_summary = load_map_summary()
    targets = load_changed_targets()
    changed_total = int(targets.get("changed_total") or 0)
    new_objects_total = int(targets.get("new_objects_total") or 0)
    repost_total = sum(
        1
        for item in targets.get("items") or []
        if isinstance(item, dict) and "перевыкладка" in (item.get("changed_parts") or [])
    )
    changed_items = format_changed_items(targets)
    new_objects = format_new_objects(targets)
    lines = ["Проверка завершена."]
    if new_objects_total:
        lines.append("")
        lines.append(f"Новые объекты в Telegram: {new_objects_total}.")
        if new_objects:
            lines.append(new_objects)
    else:
        lines.append("")
        lines.append("Новых объектов не найдено.")
    if changed_total:
        lines.append("")
        if repost_total:
            lines.append(f"Переопубликованные старые объекты: {repost_total}.")
        lines.append(f"Новые изменения в Telegram: {changed_total} объект(ов).")
        if changed_items:
            lines.append(changed_items)
    else:
        lines.append("")
        lines.append("Новых правок в Telegram-постах не найдено.")

    lines.append("")
    lines.append("Технический аудит сайта:")
    lines.append("- тексты и цены: проверены")
    lines.append(f"- медиа: {'проверено' if media_report.exists() else media_note}")
    if map_summary:
        lines.append(
            f"- карта: {'есть изменения' if map_summary.get('has_changes') else 'без изменений'} "
            f"({map_summary.get('fresh_points', 0)} точек)"
        )
    return "\n".join(lines)


async def check_updates() -> tuple[str, list[CommandResult]]:
    steps: list[tuple[str, list[str]]] = [
        ("watch-telegram", [sys.executable, "scripts/watch_telegram_updates.py"]),
        ("check-map", [sys.executable, "scripts/sync_objects_map_points.py"]),
    ]
    if not CONFIG.auto_apply:
        steps.extend(
            [
                ("audit-parity", [sys.executable, "scripts/audit_telegram_site_parity.py"]),
                ("audit-prices", [sys.executable, "scripts/audit_telegram_site_prices.py"]),
                ("verify-media", [sys.executable, "tools/verify_object_media.py"]),
            ]
        )

    step_timeouts = {
        "watch-telegram": CONFIG.command_timeout_seconds,
        "check-map": CONFIG.check_timeout_seconds,
    }
    results: list[CommandResult] = []
    for name, command in steps:
        timeout = step_timeouts.get(name, CONFIG.check_timeout_seconds)
        results.append(await run_command(name, command, timeout=timeout))
    return summarize_check(), results


def load_changed_targets() -> dict[str, object]:
    if not WATCH_TARGETS_PATH.exists():
        return {}
    try:
        payload = json.loads(WATCH_TARGETS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_map_summary() -> dict[str, object]:
    if not MAP_SUMMARY_PATH.exists():
        return {}
    try:
        payload = json.loads(MAP_SUMMARY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_map_report() -> str:
    if not MAP_REPORT_PATH.exists():
        return "Отчёт карты ещё не создан."
    return MAP_REPORT_PATH.read_text(encoding="utf-8", errors="ignore").strip()


async def apply_quick_update() -> list[CommandResult]:
    steps = [
        ("new-from-sheet", [sys.executable, "scripts/sync_new_objects_from_sheet.py", "--snapshot-only"]),
        ("filters", [sys.executable, "scripts/apply_all_filters_from_sheet.py", "--snapshot-only"]),
        ("rebuild", [sys.executable, "scripts/rebuild_from_catalog_snapshot.py"]),
        ("telegram-details", [sys.executable, "scripts/apply_telegram_detail_sections.py", "--from-audit"]),
        ("telegram-prices", [sys.executable, "scripts/sync_prices_from_telegram.py", "--all"]),
        ("podborki", [sys.executable, "scripts/build_podborki_from_filters.py"]),
        ("update-map", [sys.executable, "scripts/sync_objects_map_points.py", "--apply"]),
        ("verify-media", [sys.executable, "tools/verify_object_media.py"]),
        ("validate-snapshot", [sys.executable, "tools/validate_catalog_snapshot.py"]),
        ("accept-watch-state", [sys.executable, "scripts/watch_telegram_updates.py", "--accept-changes"]),
    ]
    results = await run_steps(steps)
    if results and results[-1].return_code != 0:
        return results
    results.extend(await commit_and_push("Автообновление сайта из Telegram и таблицы."))
    return results


async def check_map_update() -> list[CommandResult]:
    return [await run_command("check-map", [sys.executable, "scripts/sync_objects_map_points.py"])]


async def apply_map_update() -> list[CommandResult]:
    results = [await run_command("update-map", [sys.executable, "scripts/sync_objects_map_points.py", "--apply"])]
    if results[-1].return_code != 0:
        return results
    summary = load_map_summary()
    if not summary.get("has_changes"):
        results.append(note_result("update-map", "Изменений карты нет. Коммит не нужен."))
        return results
    results.extend(await commit_and_push("Обновить точки объектов на карте."))
    return results


async def apply_changed_update() -> list[CommandResult]:
    results = [
        await run_command(
            "watch-telegram",
            [sys.executable, "scripts/watch_telegram_updates.py"],
            timeout=CONFIG.command_timeout_seconds,
        )
    ]
    if results[-1].return_code != 0:
        return results

    targets = load_changed_targets()
    hotel_ids = [str(item) for item in targets.get("hotel_source_ids") or []]
    kv_topic_ids = [str(item) for item in targets.get("kv_topic_ids") or []]
    new_objects = [item for item in targets.get("new_objects") or [] if isinstance(item, dict)]
    for item in new_objects:
        kind = str(item.get("kind") or "").strip()
        if kind == "hotel":
            message_id = str(item.get("message_id") or "").strip()
            if message_id:
                hotel_ids.append(message_id)
        elif kind == "kvartira":
            topic_id = str(item.get("topic_id") or "").strip()
            if topic_id:
                kv_topic_ids.append(topic_id)
    target_slugs = [
        str(item.get("slug") or "").strip()
        for item in targets.get("items") or []
        if isinstance(item, dict) and str(item.get("slug") or "").strip()
    ]
    changed_total = int(targets.get("changed_total") or 0)
    new_objects_total = int(targets.get("new_objects_total") or 0)
    if changed_total == 0 and new_objects_total == 0:
        results.append(note_result("changed-targets", "Изменённых Telegram-постов и новых объектов нет."))
        return results
    if not hotel_ids and not kv_topic_ids:
        note = (
            "Изменения или новые объекты найдены, но нет target id для точечного sync.\n"
            "Запустите /update или /full_update."
        )
        results.append(note_result("changed-targets", note, return_code=2))
        return results

    hotel_ids = sorted(set(hotel_ids), key=int)
    kv_topic_ids = sorted(set(kv_topic_ids), key=int)

    command = [
        sys.executable,
        "scripts/run_auto_sync_pipeline.py",
        "--snapshot-only",
        "--mode",
        "targeted",
        "--force-media-refresh",
    ]
    if hotel_ids:
        command.extend(["--target-hotel-source-ids", ",".join(hotel_ids)])
    if kv_topic_ids:
        command.extend(["--target-kv-topic-ids", ",".join(kv_topic_ids)])
    if target_slugs:
        command.extend(["--supplemental-slugs", ",".join(sorted(set(target_slugs)))])
    results.append(await run_command("targeted-sync", command, timeout=CONFIG.command_timeout_seconds))
    if results[-1].return_code != 0:
        return results

    extra_steps = [
        ("podborki", [sys.executable, "scripts/build_podborki_from_filters.py"]),
        ("update-map", [sys.executable, "scripts/sync_objects_map_points.py", "--apply"]),
        ("validate-snapshot", [sys.executable, "tools/validate_catalog_snapshot.py"]),
        ("accept-watch-state", [sys.executable, "scripts/watch_telegram_updates.py", "--accept-changes"]),
    ]
    results.extend(await run_steps(extra_steps))
    if results and results[-1].return_code != 0:
        return results
    results.extend(await commit_and_push("Точечное обновление сайта из изменённых Telegram-постов."))
    return results


async def apply_full_update() -> list[CommandResult]:
    command = [
        sys.executable,
        "scripts/run_auto_sync_pipeline.py",
        "--snapshot-only",
        "--mode",
        "full",
    ]
    results = [await run_command("full-sync", command, timeout=CONFIG.command_timeout_seconds)]
    if results[-1].return_code != 0:
        return results
    results.append(await run_command("update-map", [sys.executable, "scripts/sync_objects_map_points.py", "--apply"]))
    if results[-1].return_code != 0:
        return results
    results.append(
        await run_command(
            "accept-watch-state",
            [sys.executable, "scripts/watch_telegram_updates.py", "--accept-changes"],
            timeout=CONFIG.command_timeout_seconds,
        )
    )
    if results[-1].return_code != 0:
        return results
    results.extend(await commit_and_push("Полная синхронизация сайта из Telegram."))
    return results


async def commit_and_push(message: str) -> list[CommandResult]:
    add_targets = [
        "data/catalog-snapshot.json",
        "data/catalog-index.json",
        "data/objects-map-points.json",
        "data/objects-map-geocode-cache.json",
        "index.html",
        "hotels/",
        "kvartira/",
        "podborki/",
        "sitemap.xml",
        "output/all_filters_sync_report.txt",
        "output/backfill_missing_report.txt",
        "output/podborki_from_filters_report.txt",
        "output/objects-map-unmatched.txt",
        "output/telegram_prices_audit.txt",
        "output/telegram_prices_sync_report.txt",
        "output/telegram_site_parity_audit.txt",
    ]
    results = await run_steps(
        [
            ("git-status-before", ["git", "status", "--short"]),
            ("git-add", ["git", "add", *add_targets]),
            ("git-commit", ["git", "commit", "-m", message]),
            ("git-push", ["git", "push", "origin", "main"]),
            ("git-status-after", ["git", "status", "--short"]),
        ],
        stop_on_error=False,
    )
    commit_result = next((item for item in results if item.name == "git-commit"), None)
    if commit_result and commit_result.return_code == 1:
        push_index = next((i for i, item in enumerate(results) if item.name == "git-push"), None)
        if push_index is not None:
            results = results[:push_index]
    return results


def read_result_log(result: CommandResult) -> str:
    try:
        return result.log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def relative_log_path(path: Path) -> Path | str:
    try:
        return path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return path


def extract_actionable_log_lines(log_text: str, *, limit: int = 4) -> str:
    lines = []
    for raw_line in log_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("+ "):
            continue
        if "FutureWarning:" in line or line.startswith("warnings.warn("):
            continue
        if line.startswith("[auto-sync]") and not line.endswith(": failed"):
            continue
        lines.append(line)
    if not lines:
        return ""

    priority_markers = (
        "ошибка",
        "не удалось",
        "fail",
        "failed",
        "error",
        "exception",
        "traceback",
        "timeout",
        "timed out",
        "auth",
        "permission denied",
    )
    priority = [line for line in lines if any(marker in line.lower() for marker in priority_markers) or line.startswith("- ")]
    selected = priority[:limit] if priority else lines[-limit:]
    return "; ".join(selected)


def explain_failure_from_log(label: str, log_text: str, rel_log: Path | str, return_code: int) -> str:
    if "nodename nor servname provided" in log_text or "Name or service not known" in log_text:
        return (
            f"- {label}: нет соединения с Telegram / проблема DNS. "
            f"Это временная техническая проблема проверки, сайт не сломан. Лог: {rel_log}"
        )
    if "key is not registered" in log_text or "AuthKeyUnregistered" in log_text:
        return (
            f"- {label}: Telegram-сессия больше не авторизована. "
            f"Нужно заново войти в Telegram для tg_session. Лог: {rel_log}"
        )
    if "database is locked" in log_text or "Не удалось получить lock" in log_text or "Telegram-сессия занята" in log_text:
        return (
            f"- {label}: Telegram-сессия занята другим процессом. "
            f"Проверка повторится позже; сайт не сломан. Лог: {rel_log}"
        )
    if return_code == 124 or "[timeout] process killed" in log_text:
        return f"- {label}: команда выполнялась слишком долго и была остановлена. Лог: {rel_log}"
    if "Timed out" in log_text or "timed out" in log_text or "TimeoutError" in log_text:
        return (
            f"- {label}: Telegram или внешний сервис долго не отвечал. "
            f"Обычно помогает повторить запуск позже. Лог: {rel_log}"
        )
    if "FloodWait" in log_text or "A wait of" in log_text:
        return (
            f"- {label}: Telegram временно ограничил частоту запросов. "
            f"Нужно дождаться указанной паузы и повторить запуск. Лог: {rel_log}"
        )
    if ".git/index.lock" in log_text:
        return (
            f"- {label}: Git уже занят другим процессом или после сбоя остался lock-файл. "
            f"Нужно дождаться завершения git-процесса; если его нет — удалить `.git/index.lock`. Лог: {rel_log}"
        )
    if "nothing added to commit" in log_text or "nothing to commit" in log_text:
        return f"- {label}: новых изменений для коммита нет. Сайт уже актуален. Лог: {rel_log}"
    if "non-fast-forward" in log_text or "tip of your current branch is behind" in log_text:
        return (
            f"- {label}: локальная копия отстала от GitHub. "
            f"Нужно подтянуть свежий `main` и повторить публикацию. Лог: {rel_log}"
        )
    if "git-lfs" in log_text and "not found" in log_text:
        return (
            f"- {label}: Git LFS не найден в окружении бота. "
            f"Нужно добавить путь к `git-lfs` в PATH автозапуска. Лог: {rel_log}"
        )
    if "Authentication failed" in log_text or "could not read Username" in log_text:
        return (
            f"- {label}: GitHub не принял авторизацию. "
            f"Нужно проверить доступ к репозиторию или токен. Лог: {rel_log}"
        )
    if "AccessDenied" in log_text or "NoCredentialsError" in log_text or "InvalidAccessKeyId" in log_text:
        return (
            f"- {label}: хранилище медиа не приняло ключи доступа. "
            f"Нужно проверить Yandex Object Storage env-переменные. Лог: {rel_log}"
        )
    if "S3UploadFailedError" in log_text or "upload failed" in log_text.lower():
        return (
            f"- {label}: не удалось загрузить медиа в хранилище. "
            f"Проверьте сеть, ключи Yandex Object Storage и вложенный лог. Лог: {rel_log}"
        )
    if "Permission denied" in log_text:
        return f"- {label}: не хватает прав доступа к файлу или репозиторию. Лог: {rel_log}"
    if "merge conflict" in log_text.lower() or "CONFLICT" in log_text:
        return f"- {label}: возник конфликт Git, нужен ручной разбор изменений. Лог: {rel_log}"

    detail = extract_actionable_log_lines(log_text)
    if detail:
        return f"- {label}: {detail}. Лог: {rel_log}"
    return f"- {label}: не удалось выполнить шаг. Код {return_code}. Подробности: {rel_log}"


def explain_auto_sync_failure(log_text: str) -> str | None:
    match = re.search(r"\[auto-sync\] run_id=(\d{8}-\d{6})", log_text)
    if not match:
        return None
    summary_path = ROOT / "output" / "auto-sync" / match.group(1) / "summary.json"
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    steps = payload.get("steps")
    if not isinstance(steps, list):
        return None
    failed_step_name = str(payload.get("failed_step") or "")
    failed_step = None
    for step in steps:
        if not isinstance(step, dict):
            continue
        if failed_step_name and step.get("name") == failed_step_name:
            failed_step = step
            break
        if failed_step is None and int(step.get("return_code") or 0) != 0:
            failed_step = step
    if not isinstance(failed_step, dict):
        return None

    nested_log = Path(str(failed_step.get("log_file") or ""))
    if not nested_log.is_absolute():
        nested_log = ROOT / nested_log
    try:
        nested_text = nested_log.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    step_name = str(failed_step.get("name") or failed_step_name or "auto-sync")
    return_code = int(failed_step.get("return_code") or 1)
    label = STEP_LABELS.get(step_name, step_name)
    return explain_failure_from_log(label, nested_text, relative_log_path(nested_log), return_code)


def is_no_changes_commit(result: CommandResult) -> bool:
    if result.name != "git-commit" or result.return_code != 1:
        return False
    log_text = read_result_log(result)
    return "nothing added to commit" in log_text or "nothing to commit" in log_text


def result_is_failure(result: CommandResult) -> bool:
    return result.return_code != 0 and not is_no_changes_commit(result)


def explain_failure(result: CommandResult) -> str:
    log_text = read_result_log(result)
    label = STEP_LABELS.get(result.name, result.name)
    rel_log = relative_log_path(result.log_path)

    if result.name == "changed-targets" and log_text.strip():
        return f"- {label}: {log_text.strip()} Лог: {rel_log}"
    nested_failure = explain_auto_sync_failure(log_text)
    if nested_failure:
        return nested_failure
    return explain_failure_from_log(label, log_text, rel_log, result.return_code)


def explain_bot_error(error: Exception) -> str:
    text = str(error)
    if isinstance(error, asyncio.TimeoutError):
        return "операция выполнялась слишком долго и была остановлена."
    if "Timed out" in text or "timed out" in text:
        return "Telegram или внешний сервис долго не отвечал. Попробуйте повторить позже."
    if "Conflict" in text and "getUpdates" in text:
        return "запущена ещё одна копия бота. Нужно оставить только один процесс автозапуска."
    if "Unauthorized" in text or "Invalid token" in text:
        return "Telegram-токен бота не принят. Нужно проверить токен в настройках автозапуска."
    if "database is locked" in text:
        return "Telegram-сессия занята другим процессом. Проверка повторится позже; сайт не сломан."
    if "nodename nor servname provided" in text or "Name or service not known" in text:
        return "нет соединения с Telegram / проблема DNS. Бот повторит позже; сайт не сломан."
    if "key is not registered" in text or "AuthKeyUnregistered" in text:
        return "Telegram-сессия больше не авторизована. Нужно заново войти в Telegram для tg_session."
    if text:
        return f"неожиданная ошибка: {text}"
    return "неожиданная ошибка без подробностей."


def format_results(results: list[CommandResult]) -> str:
    if not results:
        return "Технические шаги не запускались."
    no_changes = any(is_no_changes_commit(result) for result in results)
    failed = [result for result in results if result_is_failure(result)]
    if not failed:
        if no_changes:
            return "Изменений для публикации нет. Сайт уже актуален, коммит не нужен."
        return "Технически всё прошло успешно."
    lines = ["Есть проблема в технических шагах:"]
    for result in failed:
        lines.append(explain_failure(result))
    return "\n".join(lines)


def check_outcome_title(results: list[CommandResult]) -> str:
    failed = [result for result in results if result_is_failure(result)]
    if failed:
        return "Техническая проблема проверки."
    targets = load_changed_targets()
    changed_total = int(targets.get("changed_total") or 0)
    if changed_total:
        return "Новые изменения найдены."
    new_objects_total = int(targets.get("new_objects_total") or 0)
    if new_objects_total:
        return "Новые изменения найдены."
    return "Сайт актуален."


def has_pending_changes(targets: dict[str, object] | None = None) -> bool:
    payload = targets if targets is not None else load_changed_targets()
    changed_total = int(payload.get("changed_total") or 0)
    new_objects_total = int(payload.get("new_objects_total") or 0)
    if changed_total or new_objects_total:
        return True
    map_summary = load_map_summary()
    return bool(map_summary.get("has_changes"))


def apply_was_published(results: list[CommandResult]) -> bool:
    commit_result = next((item for item in results if item.name == "git-commit"), None)
    return bool(commit_result and commit_result.return_code == 0)


def should_notify_apply_results(results: list[CommandResult]) -> bool:
    if any(result_is_failure(result) for result in results):
        return True
    return apply_was_published(results)


def build_apply_report(results: list[CommandResult]) -> str:
    targets = load_changed_targets()
    changed_items = format_changed_items(targets)
    new_objects = format_new_objects(targets)
    map_summary = load_map_summary()
    lines: list[str] = []

    if apply_was_published(results):
        lines.append("Сайт обновлён и опубликован.")
    elif any(result_is_failure(result) for result in results):
        lines.append("Не удалось обновить сайт.")
    else:
        lines.append("Обновление завершено.")

    if new_objects:
        lines.append("")
        lines.append("Новые объекты:")
        lines.append(new_objects)
    if changed_items:
        lines.append("")
        lines.append("Обновлённые объекты:")
        lines.append(changed_items)
    if map_summary.get("has_changes"):
        lines.append("")
        lines.append(f"Карта: обновлено точек — {map_summary.get('fresh_points', 0)}.")

    result_text = format_results(results)
    if result_text:
        lines.append("")
        lines.append(result_text)
    return "\n".join(lines)


def is_allowed(update: Update) -> bool:
    chat_id = update.effective_chat.id if update.effective_chat else None
    return chat_id in CONFIG.allowed_chat_ids


def restricted(handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not is_allowed(update):
            if update.effective_message:
                await update.effective_message.reply_text("Нет доступа.")
            return
        await handler(update, context)

    return wrapper


async def send_long_message(bot, chat_id: int, text: str) -> None:
    chunk_size = 2400
    for start in range(0, len(text), chunk_size):
        chunk = text[start : start + chunk_size]
        for attempt in range(3):
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode=None,
                    disable_web_page_preview=True,
                    read_timeout=45,
                    write_timeout=45,
                    connect_timeout=45,
                    pool_timeout=45,
                )
                break
            except (TimedOut, NetworkError):
                if attempt == 2:
                    raise
                await asyncio.sleep(2 * (attempt + 1))


@restricted
async def start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(AUTO_MODE_TEXT, reply_markup=ReplyKeyboardRemove())


async def hourly_loop(application: Application) -> None:
    await asyncio.sleep(CONFIG.initial_check_delay_seconds)
    chat_ids = sorted(CONFIG.allowed_chat_ids)
    while True:
        try:
            if not RUN_LOCK.locked():
                async with RUN_LOCK:
                    _summary, check_results = await check_updates()
                    state = read_state()
                    state["last_check"] = {
                        "result_codes": [item.return_code for item in check_results],
                    }
                    state["last_check_at"] = datetime.now().isoformat(timespec="seconds")
                    write_state(state)

                    check_failed = any(
                        result_is_failure(result)
                        for result in check_results
                        if result.name in {"watch-telegram", "check-map"}
                    )
                    if check_failed:
                        report = "Ошибка при проверке сайта.\n\n" + format_results(check_results)
                        for chat_id in chat_ids:
                            await send_long_message(application.bot, chat_id, report)
                    elif CONFIG.auto_apply and has_pending_changes():
                        apply_results = await apply_changed_update()
                        if should_notify_apply_results(apply_results):
                            report = build_apply_report(apply_results)
                            for chat_id in chat_ids:
                                await send_long_message(application.bot, chat_id, report)
        except Exception as error:  # noqa: BLE001 - daemon must report and keep running
            for chat_id in chat_ids:
                await application.bot.send_message(
                    chat_id=chat_id,
                    text="Ошибка бота обновления: " + explain_bot_error(error),
                )
        await asyncio.sleep(CONFIG.interval_seconds)


def build_application() -> Application:
    application = Application.builder().token(CONFIG.token).build()
    application.add_handler(CommandHandler("start", start))
    return application


async def notify_auto_mode(application: Application) -> None:
    for chat_id in sorted(CONFIG.allowed_chat_ids):
        try:
            await application.bot.send_message(
                chat_id=chat_id,
                text=AUTO_MODE_TEXT,
                reply_markup=ReplyKeyboardRemove(),
            )
        except (TimedOut, NetworkError):
            pass


async def run_bot() -> None:
    application = build_application()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    await application.initialize()
    if application.updater is None:
        raise RuntimeError("Telegram updater is not available")
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    await application.start()
    await notify_auto_mode(application)
    application.create_task(hourly_loop(application))
    try:
        await stop_event.wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


def main() -> int:
    asyncio.run(run_bot())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
