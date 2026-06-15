# Supabase — архив (не используется в продакшене)

**Статус:** проект мигрирован на `data/catalog-snapshot.json` + Яндекс Object Storage. Supabase не нужен для работы сайта.

## Что осталось в этой папке

| Файл | Назначение |
|------|------------|
| `schema.sql` | Историческая схема Postgres (архив) |
| `browser-client.js` | Legacy REST-клиент (не подключать на сайте) |
| `maps-config.example.js` | Перенесён в `config/maps-config.example.js` |

## Рабочая архитектура

- Каталог: `data/catalog-snapshot.json`
- Медиа: `https://storage.yandexcloud.net/abhazbereg-media/media/...`
- Sync: `python3 scripts/run_auto_sync_pipeline.py --snapshot-only`
- Rebuild: `python3 scripts/rebuild_from_catalog_snapshot.py`

## Финальный архив перед pause проекта

```bash
python3 scripts/export_supabase_archive.py
# → output/supabase_archive_YYYY-MM-DD/
```

## Ручные шаги в Dashboard Supabase

1. Убедиться, что bucket `site-media` пуст или удалён (медиа на Яндексе).
2. Pause project или downgrade тарифа.
3. Секреты `.env.supabase.local` больше не нужны для sync — только `.env.yandex.local`.

## Legacy-скрипты (только для архива)

- `scripts/export_supabase_seed.py`
- `scripts/import_to_supabase.py`
- `scripts/rebuild_from_supabase.py` — заменён `rebuild_from_catalog_snapshot.py`
