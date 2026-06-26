#!/usr/bin/env python3
"""Telegram bot for scheduled site update checks and manual sync runs on VPS."""
from __future__ import annotations

import asyncio
import json
import os
import shlex
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env.site-update-bot"
STATE_PATH = ROOT / "output" / "site-update-bot-state.json"
LOG_DIR = ROOT / "output" / "site-update-bot"
WATCH_REPORT_PATH = ROOT / "output" / "telegram-watch-report.txt"
WATCH_TARGETS_PATH = ROOT / "output" / "telegram-watch-changed-targets.json"


@dataclass
class BotConfig:
    token: str
    allowed_chat_ids: set[int]
    interval_seconds: int
    auto_apply: bool
    snapshot_only: bool
    command_timeout_seconds: int


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
        auto_apply=bool_env("SITE_UPDATE_AUTO_APPLY", False),
        snapshot_only=bool_env("SITE_UPDATE_SNAPSHOT_ONLY", True),
        command_timeout_seconds=int(os.getenv("SITE_UPDATE_COMMAND_TIMEOUT_SECONDS", "21600")),
    )


CONFIG = load_config()
RUN_LOCK = asyncio.Lock()


def command_env() -> dict[str, str]:
    load_env_file(ROOT / ".env.supabase.local")
    load_env_file(ROOT / ".env.yandex.local")
    env = os.environ.copy()
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


def summarize_check() -> str:
    parity_mismatches = count_report_markers(
        ROOT / "output" / "telegram_site_parity_audit.txt",
        ("MISMATCH",),
    )
    price_mismatches = count_report_markers(
        ROOT / "output" / "telegram_prices_audit.txt",
        ("MISMATCH", "NO_SITE_PRICES"),
    )
    media_report = ROOT / "output" / "hidden_listings_report.txt"
    media_note = "медиа-проверка выполнена" if media_report.exists() else "медиа-проверка без отчета"
    return "\n\n".join(
        [
            read_watch_report(),
            (
                f"Аудит сайта завершён.\n"
                f"Текстовые расхождения: {parity_mismatches}\n"
                f"Расхождения цен: {price_mismatches}\n"
                f"{media_note}"
            ),
        ]
    )


async def check_updates() -> tuple[str, list[CommandResult]]:
    steps = [
        ("watch-telegram", [sys.executable, "scripts/watch_telegram_updates.py"]),
        ("audit-parity", [sys.executable, "scripts/audit_telegram_site_parity.py"]),
        ("audit-prices", [sys.executable, "scripts/audit_telegram_site_prices.py"]),
        ("verify-media", [sys.executable, "tools/verify_object_media.py"]),
    ]
    results = await run_steps(steps, stop_on_error=False)
    return summarize_check(), results


def load_changed_targets() -> dict[str, object]:
    if not WATCH_TARGETS_PATH.exists():
        return {}
    try:
        payload = json.loads(WATCH_TARGETS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


async def apply_quick_update() -> list[CommandResult]:
    steps = [
        ("new-from-sheet", [sys.executable, "scripts/sync_new_objects_from_sheet.py", "--snapshot-only"]),
        ("filters", [sys.executable, "scripts/apply_all_filters_from_sheet.py", "--snapshot-only"]),
        ("rebuild", [sys.executable, "scripts/rebuild_from_catalog_snapshot.py"]),
        ("telegram-details", [sys.executable, "scripts/apply_telegram_detail_sections.py", "--from-audit"]),
        ("telegram-prices", [sys.executable, "scripts/sync_prices_from_telegram.py", "--all"]),
        ("podborki", [sys.executable, "scripts/build_podborki_from_filters.py"]),
        ("verify-media", [sys.executable, "tools/verify_object_media.py"]),
        ("validate-snapshot", [sys.executable, "tools/validate_catalog_snapshot.py"]),
        ("accept-watch-state", [sys.executable, "scripts/watch_telegram_updates.py", "--accept-changes"]),
    ]
    results = await run_steps(steps)
    if results and results[-1].return_code != 0:
        return results
    results.extend(await commit_and_push("Автообновление сайта из Telegram и таблицы."))
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


def format_results(results: list[CommandResult]) -> str:
    lines = []
    for result in results:
        status = "OK" if result.return_code == 0 else f"ERROR {result.return_code}"
        rel_log = result.log_path.relative_to(ROOT)
        lines.append(f"- {result.name}: {status} (`{rel_log}`)")
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
    chunk_size = 3500
    for start in range(0, len(text), chunk_size):
        await bot.send_message(
            chat_id=chat_id,
            text=text[start : start + chunk_size],
            parse_mode=None,
            disable_web_page_preview=True,
        )


@restricted
async def start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Бот обновления сайта.\n\n"
        "/check - проверить расхождения\n"
        "/update_changed - обновить только изменённые Telegram-посты\n"
        "/update - быстро обновить тексты, цены, фильтры и подборки\n"
        "/full_update - полный синк Telegram с медиа (долго)\n"
        "/status - состояние бота"
    )


@restricted
async def status(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    state = read_state()
    running = RUN_LOCK.locked()
    await update.effective_message.reply_text(
        f"Статус: {'занят' if running else 'свободен'}\n"
        f"Проверка каждые {CONFIG.interval_seconds // 60} мин.\n"
        f"Автоприменение: {'включено' if CONFIG.auto_apply else 'выключено'}\n"
        f"Последняя проверка: {state.get('last_check_at', 'нет')}"
    )


@restricted
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if RUN_LOCK.locked():
        await update.effective_message.reply_text("Уже выполняется другая операция.")
        return
    async with RUN_LOCK:
        await update.effective_message.reply_text("Запускаю проверку...")
        summary, results = await check_updates()
        await send_long_message(context.bot, update.effective_chat.id, summary + "\n\n" + format_results(results))


@restricted
async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if RUN_LOCK.locked():
        await update.effective_message.reply_text("Уже выполняется другая операция.")
        return
    async with RUN_LOCK:
        await update.effective_message.reply_text("Запускаю быстрое обновление сайта...")
        results = await apply_quick_update()
        await send_long_message(context.bot, update.effective_chat.id, "Быстрое обновление завершено.\n\n" + format_results(results))


@restricted
async def update_changed_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if RUN_LOCK.locked():
        await update.effective_message.reply_text("Уже выполняется другая операция.")
        return
    async with RUN_LOCK:
        await update.effective_message.reply_text("Проверяю изменённые Telegram-посты и запускаю точечное обновление...")
        results = await apply_changed_update()
        await send_long_message(
            context.bot,
            update.effective_chat.id,
            "Точечное обновление завершено.\n\n" + format_results(results),
        )


@restricted
async def full_update_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if RUN_LOCK.locked():
        await update.effective_message.reply_text("Уже выполняется другая операция.")
        return
    async with RUN_LOCK:
        await update.effective_message.reply_text("Запускаю полный синк. Это может занять несколько часов.")
        results = await apply_full_update()
        await send_long_message(context.bot, update.effective_chat.id, "Полный синк завершен.\n\n" + format_results(results))


async def hourly_loop(application: Application) -> None:
    await asyncio.sleep(10)
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
                await application.bot.send_message(chat_id=chat_id, text=f"Ошибка бота обновления: {error}")
        await asyncio.sleep(CONFIG.interval_seconds)


async def post_init(application: Application) -> None:
    application.create_task(hourly_loop(application))


def main() -> int:
    application = Application.builder().token(CONFIG.token).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("update_changed", update_changed_command))
    application.add_handler(CommandHandler("update", update_command))
    application.add_handler(CommandHandler("full_update", full_update_command))
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
