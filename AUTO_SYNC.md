# Автообновление каталога (Telegram → сайт)

## Что внедрено

Оркестратор:

- `scripts/run_auto_sync_pipeline.py`

Скрипты автозапуска (macOS `launchd`):

- `scripts/install_auto_sync_launchd.sh`
- `scripts/uninstall_auto_sync_launchd.sh`

Пайплайн выполняет по шагам:

1. `sync_catalog_from_telegram.py` (или `sync_new_objects_from_sheet.py` в режиме `new-from-sheet`)
2. `apply_all_filters_from_sheet.py` (если есть Google service account JSON)
3. `verify_object_media.py`
4. В режиме **snapshot-only**: `rebuild_from_catalog_snapshot.py` + `validate_catalog_snapshot.py`

Отчёты каждого прогона:

- `output/auto-sync/<run_id>/summary.txt`
- `output/auto-sync/<run_id>/summary.json`
- логи `01-sync.log`, `02-filters.log`, `03-verify.log` (и `04-rebuild.log`, `05-validate.log` при snapshot-only).

## Источник правды (без Supabase)

| Слой | Файл / сервис |
|------|----------------|
| Тексты и медиа новых объектов | Telegram (`@abhazbooking`, `@abhkvartira`) |
| Фильтры | Google Sheet «СОЦСЕТИ» |
| Рабочая база каталога | `data/catalog-snapshot.json` |
| Главная и каталог | `index.html`, `kvartira/index.html` (build artifacts) |

По умолчанию sync **дублирует** запись в Supabase и snapshot. Для полного отказа от Supabase используйте `--snapshot-only` или `SKIP_SUPABASE_SYNC=1`.

## Быстрый ручной запуск

```bash
cd "/Users/darya_botova/Documents/GitHub/lending_pervyi"
source .venv/bin/activate
python3 scripts/run_auto_sync_pipeline.py --mode full
```

Только snapshot (без `.env.supabase.local`):

```bash
python3 scripts/run_auto_sync_pipeline.py --mode full --snapshot-only
```

Точечный режим (пример):

```bash
python3 scripts/run_auto_sync_pipeline.py \
  --mode targeted \
  --target-hotel-source-ids "3736,3678" \
  --force-media-refresh \
  --snapshot-only
```

## Только новые объекты из «СОЦСЕТИ»

Полный синк канала **не нужен**. Backfill по строкам таблицы, фильтры, rebuild:

```bash
python3 scripts/sync_new_objects_from_sheet.py --snapshot-only
```

Через оркестратор:

```bash
python3 scripts/run_auto_sync_pipeline.py --mode new-from-sheet --snapshot-only
```

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `SKIP_SUPABASE_SYNC=1` | Не писать в Postgres; читать/писать `catalog-snapshot.json` |
| `TARGET_HOTEL_SOURCE_IDS` | Точечный синк отелей |
| `TARGET_KV_TOPIC_IDS` | Точечный синк квартир |
| `FORCE_MEDIA_REFRESH=1` | Перезагрузить медиа |

## Включение автозапуска (каждые 3 часа)

```bash
cd "/Users/darya_botova/Documents/GitHub/lending_pervyi"
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

Если `launchd` падает с `Operation not permitted` на `.venv/pyvenv.cfg` (ограничения macOS к `Documents` для фоновых агентов), используйте альтернативу ниже.

## Отключение автозапуска

```bash
bash scripts/uninstall_auto_sync_launchd.sh
```

## Альтернатива launchd (фоновый демон из текущей сессии)

```bash
bash scripts/start_auto_sync_daemon.sh
bash scripts/start_auto_sync_daemon.sh 3600   # каждый час
bash scripts/stop_auto_sync_daemon.sh
```

## Требования

1. **Snapshot-only:** файл `data/catalog-snapshot.json`, `.env.yandex.local` для загрузки медиа в Object Storage.
2. **Dual-write (legacy):** `.env.supabase.local` с `SUPABASE_URL` и `SUPABASE_SERVICE_ROLE_KEY`.
3. Telegram-сессия: `tg_session.session`
4. Для фильтров — Google service account JSON:
   - `GOOGLE_SERVICE_ACCOUNT_JSON=/abs/path/to/file.json`
   - или один из дефолтных путей в `apply_all_filters_from_sheet.py`.

## Проверка snapshot после sync

```bash
python3 tools/validate_catalog_snapshot.py
python3 scripts/rebuild_from_catalog_snapshot.py
```
