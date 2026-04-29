# Автообновление каталога (Telegram -> сайт)

## Что внедрено

Добавлен оркестратор:

- `/Users/darya_botova/Documents/New project/scripts/run_auto_sync_pipeline.py`

И скрипты автозапуска (macOS `launchd`):

- `/Users/darya_botova/Documents/New project/scripts/install_auto_sync_launchd.sh`
- `/Users/darya_botova/Documents/New project/scripts/uninstall_auto_sync_launchd.sh`

Пайплайн выполняет по шагам:

1. `sync_catalog_from_telegram.py`
2. `apply_all_filters_from_sheet.py` (если есть доступ к Google service account JSON)
3. `verify_object_media.py`

Отчёты каждого прогона:

- `/Users/darya_botova/Documents/New project/output/auto-sync/<run_id>/summary.txt`
- `/Users/darya_botova/Documents/New project/output/auto-sync/<run_id>/summary.json`
- и логи `01-sync.log`, `02-filters.log`, `03-verify.log`.

## Быстрый ручной запуск

```bash
cd "/Users/darya_botova/Documents/New project"
source .venv/bin/activate
python scripts/run_auto_sync_pipeline.py --mode full
```

Точечный режим (пример):

```bash
python scripts/run_auto_sync_pipeline.py \
  --mode targeted \
  --target-hotel-source-ids "3736,3678" \
  --force-media-refresh
```

## Включение автозапуска (каждые 3 часа)

```bash
cd "/Users/darya_botova/Documents/New project"
bash scripts/install_auto_sync_launchd.sh
```

Для другого интервала передайте секунды, например 1 час:

```bash
bash scripts/install_auto_sync_launchd.sh 3600
```

Проверка:

```bash
launchctl list | grep ru.abhazbereg.autosync
```

Если `launchd` падает с `Operation not permitted` на `.venv/pyvenv.cfg` (ограничения доступа macOS к `Documents` для фоновых агентов), используйте альтернативу ниже.

## Отключение автозапуска

```bash
cd "/Users/darya_botova/Documents/New project"
bash scripts/uninstall_auto_sync_launchd.sh
```

## Альтернатива launchd (фоновый демон из текущей сессии)

Запуск (каждые 3 часа):

```bash
cd "/Users/darya_botova/Documents/New project"
bash scripts/start_auto_sync_daemon.sh
```

Запуск с другим интервалом (например, каждый час):

```bash
bash scripts/start_auto_sync_daemon.sh 3600
```

Остановка:

```bash
bash scripts/stop_auto_sync_daemon.sh
```

## Требования

1. В `/Users/darya_botova/Documents/New project/.env.supabase.local` должны быть:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
2. Должна существовать telegram-сессия:
   - `/Users/darya_botova/Documents/New project/tg_session.session`
3. Для шага фильтров нужен Google service account JSON:
   - `GOOGLE_SERVICE_ACCOUNT_JSON=/abs/path/to/file.json`
   - либо один из дефолтных путей, указанных в `apply_all_filters_from_sheet.py`.
