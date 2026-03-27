# Supabase для сайта `абхазберег.рф`

Этот слой подготовлен так, чтобы текущий статический сайт продолжал работать, а данные можно было постепенно перенести в `Supabase`.

## Что уже подготовлено

- SQL-схема: `/Users/darya_botova/Documents/New project/supabase/schema.sql`
- Пример переменных: `/Users/darya_botova/Documents/New project/.env.supabase.example`
- Экспорт локальных данных в единый seed: `/Users/darya_botova/Documents/New project/scripts/export_supabase_seed.py`
- Импорт seed в базу: `/Users/darya_botova/Documents/New project/scripts/import_to_supabase.py`
- Загрузка фото и видео в `Supabase Storage`: `/Users/darya_botova/Documents/New project/scripts/upload_media_to_supabase.py`
- Браузерный клиент для чтения из Supabase: `/Users/darya_botova/Documents/New project/supabase/browser-client.js`

## Что хранится в базе

### `public.listings`

Единая таблица для отелей и квартир.

Основные поля:
- `source_kind`: `hotel` или `kvartira`
- `source_channel`: `abhazbooking` или `abhkvartira`
- `source_message_id`: ID поста в Telegram
- `source_topic_id`: ID темы форума Telegram, если есть
- `slug`: локальный slug сайта
- `title`, `summary`, `excerpt`
- `city`, `location_text`, `distance_text`, `beach_text`, `capacity_text`
- `page_url`, `telegram_url`
- `published_at`
- `cover_url`
- `details jsonb`

### `public.listing_media`

Все фото и видео, связанные с объектом.

Основные поля:
- `listing_id`
- `media_role`: `card`, `gallery`, `video`, `cover`
- `storage_bucket`, `storage_path`
- `public_url`
- `source_url`

## Порядок подключения

### 1. Создайте проект Supabase

Нужны:
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

### 2. Выполните SQL-схему

Откройте SQL Editor в Supabase и выполните файл:
- `/Users/darya_botova/Documents/New project/supabase/schema.sql`

Он создаст:
- таблицы `listings` и `listing_media`
- индексы
- RLS-политики на публичное чтение
- публичный bucket `site-media`

### 3. Сгенерируйте нормализованный seed из текущего сайта

```bash
python3 "/Users/darya_botova/Documents/New project/scripts/export_supabase_seed.py"
```

Результат:
- `/Users/darya_botova/Documents/New project/output/supabase_seed.json`

### 4. Импортируйте данные в Supabase

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
python3 "/Users/darya_botova/Documents/New project/scripts/import_to_supabase.py"
```

### 5. Загрузите фото и видео в Storage

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
export SUPABASE_STORAGE_BUCKET="site-media"
python3 "/Users/darya_botova/Documents/New project/scripts/upload_media_to_supabase.py"
```

## Как подключать на фронтенде

Если захотите читать каталог прямо из Supabase в браузере:

1. Создайте глобальный конфиг в отдельном файле, который не будет храниться в публичном репозитории как секретный серверный ключ:

```html
<script>
  window.__ABHAZBEREG_SUPABASE_CONFIG__ = {
    url: 'https://your-project.supabase.co',
    anonKey: 'your-public-anon-key'
  };
</script>
<script src="/supabase/browser-client.js"></script>
```

2. После этого в браузере будет доступен объект:

```js
await window.ABHAZBEREG_SUPABASE.fetchListings({ sourceKind: 'hotel' })
await window.ABHAZBEREG_SUPABASE.fetchListings({ sourceKind: 'kvartira' })
await window.ABHAZBEREG_SUPABASE.fetchListingBySlug('pegas-otel-na-pervoy-linii-vid-na-more-2574')
```

## Важное ограничение текущего этапа

Сейчас это переходный слой.

То есть:
- текущий сайт все еще работает как статический
- `Supabase` уже можно наполнить этими же данными
- следующий этап — заменить статическую генерацию карточек и страниц на чтение из базы

Это намеренно сделано так, чтобы не сломать продакшн во время миграции.
