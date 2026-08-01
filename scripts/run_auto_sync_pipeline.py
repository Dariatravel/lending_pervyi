#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "auto-sync"
ENV_PATH = ROOT / ".env.supabase.local"
DEFAULT_GOOGLE_CREDS = [
    ROOT / "google-service-account.json",
    Path("/Users/darya_botova/Downloads/sonorous-bounty-488706-q9-32a19387de8d.json"),
    Path("/Users/darya_botova/Documents/ПОДБОРКИ/telegram_export/credentials.json"),
]


@dataclass
class StepResult:
    name: str
    command: str
    log_file: str
    return_code: int
    status: str


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _has_google_creds() -> bool:
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw and Path(raw).exists():
        return True
    return any(path.exists() for path in DEFAULT_GOOGLE_CREDS)


def _run_step(
    *,
    name: str,
    cmd: Sequence[str],
    env: dict[str, str],
    log_path: Path,
    dry_run: bool,
) -> StepResult:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command_str = " ".join(cmd)
    if dry_run:
        log_path.write_text(f"[dry-run] {command_str}\n", encoding="utf-8")
        return StepResult(
            name=name,
            command=command_str,
            log_file=str(log_path),
            return_code=0,
            status="dry-run",
        )

    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )
    if process.returncode == 0:
        # Предупреждения шагов (например, «не удалось загрузить фото») иначе
        # остаются в недоступном лог-файле раннера.
        try:
            warns = [l for l in log_path.read_text(encoding="utf-8").splitlines() if "[warn]" in l.lower()]
            for line in warns[:40]:
                print(f"[auto-sync] warn {name}: {line}", flush=True)
            if len(warns) > 40:
                print(f"[auto-sync] warn {name}: ... и ещё {len(warns) - 40}", flush=True)
        except OSError:
            pass
    if process.returncode != 0:
        # На CI лог-файлы шагов недоступны после завершения run'а — печатаем
        # хвост упавшего шага прямо в stdout, иначе причину не найти.
        try:
            tail = log_path.read_text(encoding="utf-8").splitlines()[-80:]
            print(f"[auto-sync] ---- хвост лога шага {name} ({log_path.name}) ----", flush=True)
            for line in tail:
                print(f"[auto-sync] | {line}", flush=True)
            print(f"[auto-sync] ---- конец лога шага {name} ----", flush=True)
        except OSError:
            pass
    return StepResult(
        name=name,
        command=command_str,
        log_file=str(log_path),
        return_code=process.returncode,
        status="ok" if process.returncode == 0 else "failed",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Автопайплайн обновления каталога: Telegram синк -> фильтры из Google Sheet "
            "-> проверка медиапривязки."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("full", "targeted", "new-from-sheet"),
        default="full",
        help=(
            "full = полный синк канала/форума; targeted = точечный по ID; "
            "new-from-sheet = только строки таблицы без объекта в базе (backfill_missing_from_sheet_links + фильтры + rebuild)."
        ),
    )
    parser.add_argument(
        "--target-hotel-source-ids",
        default="",
        help="Список source_id отелей через запятую (для targeted).",
    )
    parser.add_argument(
        "--target-kv-topic-ids",
        default="",
        help="Список topic_id квартир через запятую (для targeted).",
    )
    parser.add_argument(
        "--force-media-refresh",
        action="store_true",
        help="Перезагружать медиа даже если файл уже есть.",
    )
    parser.add_argument(
        "--skip-filters",
        action="store_true",
        help="Не применять фильтры из Google Sheets.",
    )
    parser.add_argument(
        "--strict-filters",
        action="store_true",
        help="Падать, если шаг применения фильтров завершился ошибкой.",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Пропустить verify_object_media.py",
    )
    parser.add_argument(
        "--skip-supplemental-comments",
        action="store_true",
        help="Не восстанавливать блоки фото из комментариев Telegram после targeted sync.",
    )
    parser.add_argument(
        "--skip-review-banks",
        action="store_true",
        help="Не собирать и не выгружать CDN-банки отзывов.",
    )
    parser.add_argument(
        "--skip-page-health",
        action="store_true",
        help="Не запускать финальные guardrail-проверки HTML/CSS/JS.",
    )
    parser.add_argument(
        "--supplemental-slugs",
        default="",
        help="Slug объектов через запятую для apply_telegram_supplemental_comments.py --force.",
    )
    parser.add_argument(
        "--verify-check-files",
        action="store_true",
        help="Добавить в verify проверку наличия локальных photo-01.jpg.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Показать команды без запуска.",
    )
    parser.add_argument(
        "--snapshot-only",
        action="store_true",
        help="Писать в catalog-snapshot.json без Supabase (SKIP_SUPABASE_SYNC=1).",
    )
    parser.add_argument(
        "--skip-podborki",
        action="store_true",
        help="Не пересобирать страницы /podborki/ (обычно они собираются после каталога).",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    env_file_data = _load_env(ENV_PATH)
    snapshot_only = args.snapshot_only or os.getenv("SKIP_SUPABASE_SYNC", "").strip().lower() in {"1", "true", "yes", "on"}
    if not snapshot_only and ("SUPABASE_URL" not in env_file_data or "SUPABASE_SERVICE_ROLE_KEY" not in env_file_data):
        if not (ROOT / "data" / "catalog-snapshot.json").exists():
            print(
                "Ошибка: нужен .env.supabase.local или --snapshot-only с data/catalog-snapshot.json.",
                file=sys.stderr,
            )
            return 2
        snapshot_only = True

    run_id = _timestamp()
    run_dir = OUTPUT_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "summary.json"
    summary_txt_path = run_dir / "summary.txt"

    base_env = os.environ.copy()
    base_env.update(env_file_data)
    if snapshot_only:
        base_env["SKIP_SUPABASE_SYNC"] = "1"
    # Дефолтный таймаут Telegram-скриптов (30 мин) мал не только для полного
    # прохода, но и для точечного синка пачки отелей с видео — поднимаем всегда.
    base_env.setdefault(
        "TG_SCRIPT_TIMEOUT_SECONDS",
        base_env.get("SITE_UPDATE_COMMAND_TIMEOUT_SECONDS", "21600"),
    )

    python = sys.executable
    steps: list[StepResult] = []

    def append_review_bank_step(step_index: str) -> int:
        if args.skip_review_banks:
            path = run_dir / f"{step_index}-review-banks.log"
            path.write_text("SKIPPED (--skip-review-banks)\n", encoding="utf-8")
            step = StepResult(
                name="build_cdn_review_banks",
                command="SKIPPED (--skip-review-banks)",
                log_file=str(path),
                return_code=0,
                status="skipped",
            )
        else:
            cmd = [python, str(ROOT / "tools" / "build_cdn_review_banks.py"), "--upload", "--check"]
            if args.dry_run:
                cmd.append("--dry-run")
            step = _run_step(
                name="build_cdn_review_banks",
                cmd=cmd,
                env=base_env,
                log_path=run_dir / f"{step_index}-review-banks.log",
                dry_run=args.dry_run,
            )
        steps.append(step)
        print(f"[auto-sync] {step.name}: {step.status}")
        return step.return_code

    def append_page_health_step(step_index: str) -> int:
        if args.skip_page_health:
            path = run_dir / f"{step_index}-page-health.log"
            path.write_text("SKIPPED (--skip-page-health)\n", encoding="utf-8")
            step = StepResult(
                name="check_page_health",
                command="SKIPPED (--skip-page-health)",
                log_file=str(path),
                return_code=0,
                status="skipped",
            )
        else:
            step = _run_step(
                name="check_page_health",
                cmd=[python, str(ROOT / "tools" / "check_page_health.py")],
                env=base_env,
                log_path=run_dir / f"{step_index}-page-health.log",
                dry_run=args.dry_run,
            )
        steps.append(step)
        print(f"[auto-sync] {step.name}: {step.status}")
        return step.return_code

    def write_failed_summary(failed_step: StepResult) -> None:
        payload = {
            "run_id": run_id,
            "status": "failed",
            "failed_step": failed_step.name,
            "steps": [asdict(step) for step in steps],
        }
        summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_txt_path.write_text(
            f"run_id: {run_id}\nstatus: failed\nfailed_step: {failed_step.name}\n",
            encoding="utf-8",
        )

    print(f"[auto-sync] run_id={run_id}")
    if snapshot_only:
        print("[auto-sync] режим: snapshot-only (без Supabase)")

    if args.mode == "new-from-sheet":
        cred = env_file_data.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip() or str(ROOT / "google-service-account.json")
        if Path(cred).exists():
            base_env["GOOGLE_SERVICE_ACCOUNT_JSON"] = cred
        sync_cmd = [python, str(ROOT / "scripts" / "sync_new_objects_from_sheet.py")]
        if snapshot_only:
            sync_cmd.append("--snapshot-only")
        if args.skip_verify:
            sync_cmd.append("--skip-verify")
        if args.skip_filters:
            sync_cmd.append("--skip-filters")
        sync_result = _run_step(
            name="sync_new_objects_from_sheet",
            cmd=sync_cmd,
            env=base_env,
            log_path=run_dir / "01-new-from-sheet.log",
            dry_run=args.dry_run,
        )
        steps.append(sync_result)
        print(f"[auto-sync] {sync_result.name}: {sync_result.status}")
        if sync_result.return_code != 0 and not args.dry_run:
            write_failed_summary(sync_result)
            return sync_result.return_code
        for idx, runner in (("02", append_review_bank_step), ("03", append_page_health_step)):
            rc = runner(idx)
            if rc != 0 and not args.dry_run:
                write_failed_summary(steps[-1])
                return rc
        payload_ok = {"run_id": run_id, "status": "ok", "steps": [asdict(step) for step in steps]}
        summary_path.write_text(json.dumps(payload_ok, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = [f"run_id: {run_id}", "status: ok", ""]
        for step in steps:
            lines.append(f"- {step.name}: {step.status} (rc={step.return_code})")
            lines.append(f"  log: {step.log_file}")
        summary_txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[auto-sync] completed, отчёт: {summary_txt_path}")
        return 0

    if args.mode == "targeted":
        if not args.target_hotel_source_ids and not args.target_kv_topic_ids:
            print(
                "Ошибка: для --mode targeted укажите --target-hotel-source-ids и/или --target-kv-topic-ids.",
                file=sys.stderr,
            )
            return 2
        base_env["TARGET_HOTEL_SOURCE_IDS"] = args.target_hotel_source_ids
        base_env["TARGET_KV_TOPIC_IDS"] = args.target_kv_topic_ids
    else:
        base_env.pop("TARGET_HOTEL_SOURCE_IDS", None)
        base_env.pop("TARGET_KV_TOPIC_IDS", None)

    if args.force_media_refresh:
        base_env["FORCE_MEDIA_REFRESH"] = "1"

    sync_result = _run_step(
        name="sync_catalog_from_telegram",
        cmd=[python, str(ROOT / "scripts" / "sync_catalog_from_telegram.py")],
        env=base_env,
        log_path=run_dir / "01-sync.log",
        dry_run=args.dry_run,
    )
    steps.append(sync_result)
    print(f"[auto-sync] {sync_result.name}: {sync_result.status}")

    if sync_result.return_code != 0 and not args.dry_run:
        payload = {
            "run_id": run_id,
            "status": "failed",
            "failed_step": sync_result.name,
            "steps": [asdict(step) for step in steps],
        }
        summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_txt_path.write_text(
            f"run_id: {run_id}\nstatus: failed\nfailed_step: {sync_result.name}\n",
            encoding="utf-8",
        )
        return sync_result.return_code

    if args.skip_filters:
        steps.append(
            StepResult(
                name="apply_all_filters_from_sheet",
                command="SKIPPED (--skip-filters)",
                log_file=str(run_dir / "02-filters.log"),
                return_code=0,
                status="skipped",
            )
        )
    else:
        if not _has_google_creds():
            msg = "SKIPPED (нет Google service account JSON)"
            status = "skipped"
            rc = 0
            if args.strict_filters and not args.dry_run:
                msg = "FAILED (нет Google service account JSON)"
                status = "failed"
                rc = 2
            (run_dir / "02-filters.log").write_text(msg + "\n", encoding="utf-8")
            filter_step = StepResult(
                name="apply_all_filters_from_sheet",
                command=msg,
                log_file=str(run_dir / "02-filters.log"),
                return_code=rc,
                status=status,
            )
        else:
            filter_cmd = [python, str(ROOT / "scripts" / "apply_all_filters_from_sheet.py")]
            if snapshot_only:
                filter_cmd.append("--snapshot-only")
            filter_step = _run_step(
                name="apply_all_filters_from_sheet",
                cmd=filter_cmd,
                env=base_env,
                log_path=run_dir / "02-filters.log",
                dry_run=args.dry_run,
            )
            if filter_step.return_code != 0 and not args.strict_filters and not args.dry_run:
                filter_step.status = "warn"
        steps.append(filter_step)
        print(f"[auto-sync] {filter_step.name}: {filter_step.status}")
        if filter_step.return_code != 0 and args.strict_filters and not args.dry_run:
            payload = {
                "run_id": run_id,
                "status": "failed",
                "failed_step": filter_step.name,
                "steps": [asdict(step) for step in steps],
            }
            summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            summary_txt_path.write_text(
                f"run_id: {run_id}\nstatus: failed\nfailed_step: {filter_step.name}\n",
                encoding="utf-8",
            )
            return filter_step.return_code

    if args.skip_verify:
        steps.append(
            StepResult(
                name="verify_object_media",
                command="SKIPPED (--skip-verify)",
                log_file=str(run_dir / "03-verify.log"),
                return_code=0,
                status="skipped",
            )
        )
    else:
        verify_cmd = [python, str(ROOT / "tools" / "verify_object_media.py")]
        if args.verify_check_files:
            verify_cmd.append("--check-files")
        verify_step = _run_step(
            name="verify_object_media",
            cmd=verify_cmd,
            env=base_env,
            log_path=run_dir / "03-verify.log",
            dry_run=args.dry_run,
        )
        steps.append(verify_step)
        print(f"[auto-sync] {verify_step.name}: {verify_step.status}")
        if verify_step.return_code != 0 and not args.dry_run:
            payload = {
                "run_id": run_id,
                "status": "failed",
                "failed_step": verify_step.name,
                "steps": [asdict(step) for step in steps],
            }
            summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            summary_txt_path.write_text(
                f"run_id: {run_id}\nstatus: failed\nfailed_step: {verify_step.name}\n",
                encoding="utf-8",
            )
            return verify_step.return_code

    should_rebuild_catalog = snapshot_only or args.mode == "targeted"

    if should_rebuild_catalog:
        rebuild_step = _run_step(
            name="rebuild_from_catalog_snapshot",
            cmd=[python, str(ROOT / "scripts" / "rebuild_from_catalog_snapshot.py")],
            env=base_env,
            log_path=run_dir / "04-rebuild.log",
            dry_run=args.dry_run,
        )
        steps.append(rebuild_step)
        print(f"[auto-sync] {rebuild_step.name}: {rebuild_step.status}")
        if rebuild_step.return_code != 0 and not args.dry_run:
            payload = {
                "run_id": run_id,
                "status": "failed",
                "failed_step": rebuild_step.name,
                "steps": [asdict(step) for step in steps],
            }
            summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            summary_txt_path.write_text(
                f"run_id: {run_id}\nstatus: failed\nfailed_step: {rebuild_step.name}\n",
                encoding="utf-8",
            )
            return rebuild_step.return_code

        if args.mode == "targeted":
            consistency_cmd = [python, str(ROOT / "tools" / "check_catalog_location_consistency.py")]
            if args.target_hotel_source_ids:
                consistency_cmd.extend(["--hotel-source-ids", args.target_hotel_source_ids])
            if args.target_kv_topic_ids:
                consistency_cmd.extend(["--kv-topic-ids", args.target_kv_topic_ids])
            consistency_step = _run_step(
                name="check_catalog_location_consistency",
                cmd=consistency_cmd,
                env=base_env,
                log_path=run_dir / "05-location-consistency.log",
                dry_run=args.dry_run,
            )
            steps.append(consistency_step)
            print(f"[auto-sync] {consistency_step.name}: {consistency_step.status}")
            if consistency_step.return_code != 0 and not args.dry_run:
                payload = {
                    "run_id": run_id,
                    "status": "failed",
                    "failed_step": consistency_step.name,
                    "steps": [asdict(step) for step in steps],
                }
                summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                summary_txt_path.write_text(
                    f"run_id: {run_id}\nstatus: failed\nfailed_step: {consistency_step.name}\n",
                    encoding="utf-8",
                )
                return consistency_step.return_code

        validate_step = _run_step(
            name="validate_catalog_snapshot",
            cmd=[python, str(ROOT / "tools" / "validate_catalog_snapshot.py")],
            env=base_env,
            log_path=run_dir / "06-validate.log",
            dry_run=args.dry_run,
        )
        steps.append(validate_step)
        print(f"[auto-sync] {validate_step.name}: {validate_step.status}")
        if validate_step.return_code != 0 and not args.dry_run:
            payload = {
                "run_id": run_id,
                "status": "failed",
                "failed_step": validate_step.name,
                "steps": [asdict(step) for step in steps],
            }
            summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            summary_txt_path.write_text(
                f"run_id: {run_id}\nstatus: failed\nfailed_step: {validate_step.name}\n",
                encoding="utf-8",
            )
            return validate_step.return_code

        # Подборки /podborki/ собираются из полного каталога (catalog-snapshot.json),
        # поэтому обновляются вместе с ним. Шаг вторичен: его ошибка не должна
        # блокировать деплой каталога — логируем и продолжаем.
        if not args.skip_podborki:
            podborki_step = _run_step(
                name="build_podborki_from_filters",
                cmd=[python, str(ROOT / "scripts" / "build_podborki_from_filters.py")],
                env=base_env,
                log_path=run_dir / "06b-podborki.log",
                dry_run=args.dry_run,
            )
            steps.append(podborki_step)
            print(f"[auto-sync] {podborki_step.name}: {podborki_step.status}")
            if podborki_step.return_code != 0 and not args.dry_run:
                print(
                    f"[auto-sync] ВНИМАНИЕ: {podborki_step.name} упал "
                    "(подборки вторичны) — деплой каталога продолжаем."
                )

    supplemental_slugs = ",".join(
        part.strip()
        for part in (args.supplemental_slugs or "").split(",")
        if part.strip()
    )
    supplemental_audit_exists = (ROOT / "output" / "telegram_supplemental_comments_audit.json").exists()
    if args.skip_supplemental_comments or (not supplemental_slugs and not supplemental_audit_exists):
        status = "skipped"
        command = (
            "SKIPPED (--skip-supplemental-comments)"
            if args.skip_supplemental_comments
            else "SKIPPED (нет --supplemental-slugs и output/telegram_supplemental_comments_audit.json)"
        )
        (run_dir / "07-supplemental-comments.log").write_text(command + "\n", encoding="utf-8")
        supplemental_step = StepResult(
            name="apply_telegram_supplemental_comments",
            command=command,
            log_file=str(run_dir / "07-supplemental-comments.log"),
            return_code=0,
            status=status,
        )
    else:
        supplemental_cmd = [
            python,
            str(ROOT / "scripts" / "apply_telegram_supplemental_comments.py"),
            "--force",
        ]
        if supplemental_slugs:
            supplemental_cmd.extend(["--slug", supplemental_slugs])
        if args.dry_run:
            supplemental_cmd.append("--dry-run")
        supplemental_step = _run_step(
            name="apply_telegram_supplemental_comments",
            cmd=supplemental_cmd,
            env=base_env,
            log_path=run_dir / "07-supplemental-comments.log",
            dry_run=args.dry_run,
        )
    steps.append(supplemental_step)
    print(f"[auto-sync] {supplemental_step.name}: {supplemental_step.status}")
    if supplemental_step.return_code != 0 and not args.dry_run:
        write_failed_summary(supplemental_step)
        return supplemental_step.return_code

    # SEO-финишеры: пересборка страниц каждый раз возвращает шаблонные
    # описания и стирает вставленные блоки, поэтому после генераторов
    # прогоняем правки заново. Шаги вторичны — их падение не блокирует деплой.
    seo_steps = (
        ("07a", "apply_unique_page_descriptions", ROOT / "tools" / "apply_unique_page_descriptions.py"),
        ("07b", "apply_noindex_to_hidden_pages", ROOT / "tools" / "apply_noindex_to_hidden_pages.py"),
        ("07c", "apply_blog_schema_extras", ROOT / "scripts" / "apply_blog_schema_extras.py"),
        ("07d", "inject_blog_related_links", ROOT / "scripts" / "inject_blog_related_links.py"),
    )
    for idx, name, script in seo_steps:
        seo_step = _run_step(
            name=name,
            cmd=[python, str(script)] + (["--check"] if args.dry_run else []),
            env=base_env,
            log_path=run_dir / f"{idx}-{name}.log",
            dry_run=args.dry_run,
        )
        steps.append(seo_step)
        print(f"[auto-sync] {seo_step.name}: {seo_step.status}")
        if seo_step.return_code != 0 and not args.dry_run:
            print(f"[auto-sync] ВНИМАНИЕ: {seo_step.name} упал (SEO-правка вторична) — продолжаем.")

    for idx, runner in (("08", append_review_bank_step), ("09", append_page_health_step)):
        rc = runner(idx)
        if rc != 0 and not args.dry_run:
            write_failed_summary(steps[-1])
            return rc

    payload = {
        "run_id": run_id,
        "status": "ok",
        "steps": [asdict(step) for step in steps],
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"run_id: {run_id}", "status: ok", ""]
    for step in steps:
        lines.append(f"- {step.name}: {step.status} (rc={step.return_code})")
        lines.append(f"  log: {step.log_file}")
    summary_txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[auto-sync] completed, отчёт: {summary_txt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
