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

По умолчанию sync пишет в **`data/catalog-snapshot.json`** (рекомендуется `--snapshot-only`). Dual-write в Supabase — только legacy.

```bash
python3 scripts/run_auto_sync_pipeline.py --mode full --snapshot-only
```

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

1. **Snapshot-only (прод):** `data/catalog-snapshot.json`, `.env.yandex.local` для загрузки медиа.
2. Telegram-сессия: `tg_session.session`
3. Для фильтров — Google service account JSON:
   - `GOOGLE_SERVICE_ACCOUNT_JSON=/abs/path/to/file.json`
   - или один из дефолтных путей в `apply_all_filters_from_sheet.py`.

## Проверка snapshot после sync

```bash
python3 tools/validate_catalog_snapshot.py
python3 scripts/rebuild_from_catalog_snapshot.py
```

## VPS + Telegram-бот управления

Добавлен бот:

- `scripts/site_update_bot.py`
- `.env.site-update-bot.example`
- `requirements-site-update-bot.txt`
- `deploy/systemd/abhazbereg-site-update-bot.service`

Бот работает в long polling режиме. По умолчанию он **раз в час проверяет** расхождения в Telegram-постах и присылает уведомление владельцу. Обновление сайта запускается вручную из Telegram:

- `/check` — проверить расхождения сейчас;
- `/update` — быстро обновить новые объекты, фильтры, детальные тексты, цены, подборки, затем сделать commit + push;
- `/full_update` — полный синк Telegram с медиа, долго;
- `/status` — состояние бота.

Безопасный режим по умолчанию:

```env
SITE_UPDATE_AUTO_APPLY=0
```

Если нужно, чтобы бот сам применял быстрые обновления после часовой проверки:

```env
SITE_UPDATE_AUTO_APPLY=1
```

### Установка на VPS

Пример для Ubuntu, путь проекта `/srv/lending_pervyi`:

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip

cd /srv
sudo git clone git@github.com:Dariatravel/lending_pervyi.git
sudo chown -R "$USER":"$USER" /srv/lending_pervyi
cd /srv/lending_pervyi

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-site-update-bot.txt
pip install -r collab_bot/requirements.txt

cp .env.site-update-bot.example .env.site-update-bot
nano .env.site-update-bot
```

На сервер нужно положить локальные секреты:

- `.env.site-update-bot` — токен бота и разрешённые chat id;
- `.env.yandex.local` — доступ к Яндекс Object Storage для медиа;
- `google-service-account.json` — фильтры из таблицы;
- `tg_session.session` — Telegram-сессия Telethon;
- SSH deploy key с правом `git push` в репозиторий.

Проверка вручную:

```bash
source .venv/bin/activate
python3 scripts/site_update_bot.py
```

### systemd

```bash
sudo cp deploy/systemd/abhazbereg-site-update-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now abhazbereg-site-update-bot
sudo systemctl status abhazbereg-site-update-bot
```

Логи:

```bash
journalctl -u abhazbereg-site-update-bot -f
ls -lah output/site-update-bot/
```
