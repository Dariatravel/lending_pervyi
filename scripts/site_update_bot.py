#!/usr/bin/env python3
"""Telegram bot for scheduled site update checks and manual sync runs on VPS."""
from __future__ import annotations

import asyncio
import json
import os
import signal
import shlex
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

from telegram import ReplyKeyboardMarkup, Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env.site-update-bot"
STATE_PATH = ROOT / "output" / "site-update-bot-state.json"
LOG_DIR = ROOT / "output" / "site-update-bot"
WATCH_REPORT_PATH = ROOT / "output" / "telegram-watch-report.txt"
WATCH_TARGETS_PATH = ROOT / "output" / "telegram-watch-changed-targets.json"
MAP_REPORT_PATH = ROOT / "output" / "objects-map-sync-report.txt"
MAP_SUMMARY_PATH = ROOT / "output" / "objects-map-sync-summary.json"

BUTTON_STATUS = "Статус"
BUTTON_CHECK = "Проверить сайт"
BUTTON_CHECK_MAP = "Проверить карту"
BUTTON_UPDATE_CHANGED = "Обновить изменения"
BUTTON_UPDATE_MAP = "Обновить карту"
BUTTON_UPDATE = "Обновить сайт"
BUTTON_FULL_UPDATE = "Полный синк"
BUTTON_HELP = "Помощь"

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
    "accept-watch-state": "сохранение состояния проверки",
    "targeted-sync": "точечная синхронизация",
    "full-sync": "полная синхронизация",
    "git-status-before": "проверка git перед коммитом",
    "git-add": "подготовка файлов к коммиту",
    "git-commit": "коммит",
    "git-push": "публикация в GitHub",
    "git-status-after": "проверка git после коммита",
    "changed-targets": "поиск изменённых объектов",
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


def menu_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [BUTTON_CHECK, BUTTON_UPDATE_CHANGED],
            [BUTTON_CHECK_MAP, BUTTON_UPDATE_MAP],
            [BUTTON_STATUS, BUTTON_UPDATE],
            [BUTTON_FULL_UPDATE, BUTTON_HELP],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def help_text() -> str:
    return (
        "Я слежу за обновлениями сайта.\n\n"
        f"{BUTTON_CHECK} — проверить Telegram-посты, цены, тексты и медиа.\n"
        f"{BUTTON_CHECK_MAP} — проверить, изменились ли точки интерактивной карты.\n"
        f"{BUTTON_UPDATE_CHANGED} — обновить только объекты, где изменился Telegram-пост.\n"
        f"{BUTTON_UPDATE_MAP} — применить изменения точек карты и запушить сайт.\n"
        f"{BUTTON_UPDATE} — быстро обновить сайт: новые объекты, фильтры, цены, описания и подборки.\n"
        f"{BUTTON_FULL_UPDATE} — полный синк Telegram с медиа; запускать редко, это долго.\n"
        f"{BUTTON_STATUS} — показать состояние бота.\n\n"
        "Автообновление сейчас выключено: я уведомляю, а решение об обновлении остаётся за вами."
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
        lines.append(f"- {title}: {parts}")
    if len(items) > limit:
        lines.append(f"- и ещё {len(items) - limit} объект(ов)")
    return "\n".join(lines)


def summarize_check() -> str:
    media_report = ROOT / "output" / "hidden_listings_report.txt"
    media_note = "медиа-проверка выполнена" if media_report.exists() else "медиа-проверка без отчета"
    map_summary = load_map_summary()
    targets = load_changed_targets()
    changed_total = int(targets.get("changed_total") or 0)
    changed_items = format_changed_items(targets)
    lines = ["Проверка завершена."]
    if changed_total:
        lines.append("")
        lines.append(f"Новые изменения в Telegram: {changed_total} объект(ов).")
        if changed_items:
            lines.append(changed_items)
        lines.append("")
        lines.append(f"Что делать: нажмите «{BUTTON_UPDATE_CHANGED}», чтобы обновить только эти объекты.")
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
    steps = [
        ("watch-telegram", [sys.executable, "scripts/watch_telegram_updates.py"]),
        ("check-map", [sys.executable, "scripts/sync_objects_map_points.py"]),
        ("audit-parity", [sys.executable, "scripts/audit_telegram_site_parity.py"]),
        ("audit-prices", [sys.executable, "scripts/audit_telegram_site_prices.py"]),
        ("verify-media", [sys.executable, "tools/verify_object_media.py"]),
    ]
    results: list[CommandResult] = []
    for name, command in steps:
        results.append(await run_command(name, command, timeout=CONFIG.check_timeout_seconds))
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
    changed_total = int(targets.get("changed_total") or 0)
    if changed_total == 0:
        results.append(note_result("changed-targets", "Изменённых Telegram-постов нет."))
        return results
    if not hotel_ids and not kv_topic_ids:
        note = (
            "Изменения найдены, но нет target id для точечного sync.\n"
            "Запустите /update или /full_update."
        )
        results.append(note_result("changed-targets", note, return_code=2))
        return results

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
        "data/objects-map-points.json",
        "data/objects-map-geocode-cache.json",
        "index.html",
        "hotels/",
        "kvartira/",
        "podborki/",
        "sitemap.xml",
        "media/cards/",
        "media/hotels/",
        "media/kvartira/",
        "media/kvartira-cards/",
        "media/videos/",
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
    rel_log = result.log_path.relative_to(ROOT)

    if result.name == "changed-targets" and log_text.strip():
        return f"- {label}: {log_text.strip()} Лог: {rel_log}"
    if result.return_code == 124 or "[timeout] process killed" in log_text:
        return f"- {label}: команда выполнялась слишком долго и была остановлена. Лог: {rel_log}"
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
    if "Permission denied" in log_text:
        return f"- {label}: не хватает прав доступа к файлу или репозиторию. Лог: {rel_log}"
    if "merge conflict" in log_text.lower() or "CONFLICT" in log_text:
        return f"- {label}: возник конфликт Git, нужен ручной разбор изменений. Лог: {rel_log}"
    return f"- {label}: не удалось выполнить шаг. Код {result.return_code}. Подробности: {rel_log}"


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
        return "Telegram-сессия занята другим процессом. Нужно дождаться завершения синхронизации или перезапустить бот."
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
    await update.effective_message.reply_text(help_text(), reply_markup=menu_markup())


@restricted
async def status(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    state = read_state()
    running = RUN_LOCK.locked()
    await update.effective_message.reply_text(
        f"Статус: {'занят' if running else 'свободен'}\n"
        f"Проверка каждые {CONFIG.interval_seconds // 60} мин.\n"
        f"Первая автопроверка через {CONFIG.initial_check_delay_seconds // 60} мин. после запуска\n"
        f"Автоприменение: {'включено' if CONFIG.auto_apply else 'выключено'}\n"
        f"Последняя проверка: {state.get('last_check_at', 'нет')}",
        reply_markup=menu_markup(),
    )


@restricted
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if RUN_LOCK.locked():
        await update.effective_message.reply_text("Уже выполняется другая операция.")
        return
    async with RUN_LOCK:
        await update.effective_message.reply_text("Запускаю проверку. Это может занять несколько минут...")
        summary, results = await check_updates()
        await send_long_message(context.bot, update.effective_chat.id, summary + "\n\n" + format_results(results))


@restricted
async def check_map_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if RUN_LOCK.locked():
        await update.effective_message.reply_text("Уже выполняется другая операция.")
        return
    async with RUN_LOCK:
        await update.effective_message.reply_text("Проверяю точки интерактивной карты...")
        results = await check_map_update()
        await send_long_message(context.bot, update.effective_chat.id, read_map_report() + "\n\n" + format_results(results))


@restricted
async def update_map_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if RUN_LOCK.locked():
        await update.effective_message.reply_text("Уже выполняется другая операция.")
        return
    async with RUN_LOCK:
        await update.effective_message.reply_text("Обновляю точки карты и, если есть изменения, публикую сайт...")
        results = await apply_map_update()
        await send_long_message(context.bot, update.effective_chat.id, read_map_report() + "\n\n" + format_results(results))


@restricted
async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if RUN_LOCK.locked():
        await update.effective_message.reply_text("Уже выполняется другая операция.")
        return
    async with RUN_LOCK:
        await update.effective_message.reply_text("Запускаю обновление сайта. Если будут изменения, я сделаю commit и push...")
        results = await apply_quick_update()
        await send_long_message(context.bot, update.effective_chat.id, "Обновление сайта завершено.\n\n" + format_results(results))


@restricted
async def update_changed_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if RUN_LOCK.locked():
        await update.effective_message.reply_text("Уже выполняется другая операция.")
        return
    async with RUN_LOCK:
        await update.effective_message.reply_text("Проверяю изменённые Telegram-посты и обновляю только их...")
        results = await apply_changed_update()
        await send_long_message(
            context.bot,
            update.effective_chat.id,
            "Обновление изменённых объектов завершено.\n\n" + format_results(results),
        )


@restricted
async def full_update_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if RUN_LOCK.locked():
        await update.effective_message.reply_text("Уже выполняется другая операция.")
        return
    async with RUN_LOCK:
        await update.effective_message.reply_text("Запускаю полный синк. Это может занять несколько часов.")
        results = await apply_full_update()
        await send_long_message(context.bot, update.effective_chat.id, "Полный синк завершён.\n\n" + format_results(results))


@restricted
async def help_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(help_text(), reply_markup=menu_markup())


@restricted
async def button_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.effective_message.text or "").strip()
    if text == BUTTON_STATUS:
        await status(update, context)
    elif text == BUTTON_CHECK:
        await check_command(update, context)
    elif text == BUTTON_CHECK_MAP:
        await check_map_command(update, context)
    elif text == BUTTON_UPDATE_CHANGED:
        await update_changed_command(update, context)
    elif text == BUTTON_UPDATE_MAP:
        await update_map_command(update, context)
    elif text == BUTTON_UPDATE:
        await update_command(update, context)
    elif text == BUTTON_FULL_UPDATE:
        await full_update_command(update, context)
    elif text == BUTTON_HELP:
        await help_command(update, context)
    else:
        await update.effective_message.reply_text(
            "Не понял команду. Выберите действие кнопкой ниже.",
            reply_markup=menu_markup(),
        )


async def hourly_loop(application: Application) -> None:
    await asyncio.sleep(CONFIG.initial_check_delay_seconds)
    chat_ids = sorted(CONFIG.allowed_chat_ids)
    while True:
        try:
            if not RUN_LOCK.locked():
                async with RUN_LOCK:
                    summary, results = await check_updates()
                    state = read_state()
                    current = {
                        "summary": summary,
                        "result_codes": [item.return_code for item in results],
                    }
                    changed = current != state.get("last_check")
                    state["last_check"] = current
                    state["last_check_at"] = datetime.now().isoformat(timespec="seconds")
                    write_state(state)
                    if changed:
                        for chat_id in chat_ids:
                            await send_long_message(
                                application.bot,
                                chat_id,
                                "Есть изменения в проверке сайта.\n\n" + summary + "\n\n" + format_results(results),
                            )
                    if CONFIG.auto_apply and changed:
                        update_results = await apply_changed_update()
                        for chat_id in chat_ids:
                            await send_long_message(
                                application.bot,
                                chat_id,
                                "Автообновление по таймеру завершено.\n\n" + format_results(update_results),
                            )
        except Exception as error:  # noqa: BLE001 - daemon must report and keep running
            for chat_id in chat_ids:
                await application.bot.send_message(
                    chat_id=chat_id,
                    text="Ошибка бота обновления: " + explain_bot_error(error),
                )
        await asyncio.sleep(CONFIG.interval_seconds)


async def post_init(application: Application) -> None:
    application.create_task(hourly_loop(application))


def build_application() -> Application:
    application = Application.builder().token(CONFIG.token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("check_map", check_map_command))
    application.add_handler(CommandHandler("update_changed", update_changed_command))
    application.add_handler(CommandHandler("update_map", update_map_command))
    application.add_handler(CommandHandler("update", update_command))
    application.add_handler(CommandHandler("full_update", full_update_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_command))
    return application


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
