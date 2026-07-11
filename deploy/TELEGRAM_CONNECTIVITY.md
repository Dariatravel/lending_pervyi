# Telethon на Timeweb VPS: диагноз и решения

## Диагноз (2026-07-11)

Симптом: `watch-telegram` на VPS падает с `Attempt 1–6 at connecting failed:
TimeoutError`; с 8 июля бот не добавляет объекты.

Картина указывает не на таймауты, а на **DPI-фильтрацию MTProto** на маршруте
RU-хостинга: TCP до DC2 (149.154.167.220:443) открывается, но рукопожатие
обрывается (`Connection reset by peer`, `301 bytes read`), остальные DC закрыты.
Bot API (HTTPS api.telegram.org) при этом работает. Повторные попытки и рост
таймаутов не помогут — трафик MTProto режется на сети, менять надо маршрут.

## Решения (в порядке рекомендации)

### 1. GitHub Actions как раннер watch-telegram (бесплатно, уже подключено)

Раннеры GitHub — вне РФ, MTProto оттуда работает. Workflow
`.github/workflows/watch-telegram.yml` запускается каждый час, читает каналы
Telethon'ом и шлёт уведомление через Bot API, если появились изменения.
VPS-бот остаётся для остального (уведомления, деплой по расписанию).

Активация (один раз, на Mac):

    cd ~/lending_pervyi   # локальная копия с авторизованной tg_session
    python3 tools/make_tg_string_session.py

Полученную строку добавить в GitHub: репозиторий → Settings → Secrets and
variables → Actions → New repository secret:

    TG_STRING_SESSION  = <строка из скрипта>          (обязательно)
    TG_BOT_TOKEN       = <токен бота>                 (для уведомлений)
    TG_REPORT_CHAT_ID  = <chat_id отчётов>            (для уведомлений)

Проверка: Actions → Watch Telegram → Run workflow. До добавления секрета
workflow завершается зелёным с пометкой «пропускаю».

Ограничение: state между запусками хранится в Actions cache (living ~7 дней
при простое); при потере кеша один запуск уйдёт на восстановление базовой
линии — это штатно, изменений он не потеряет, только отложит на час.

Важно: строковая сессия = полный доступ к аккаунту Telegram. Только в Secrets,
никогда в код. При компрометации — Telegram → Настройки → Устройства →
завершить сессию.

### 2. SOCKS5-прокси для VPS (если нужен синк именно с VPS)

Код уже поддерживает `TG_PROXY` (scripts/telegram_runtime.py) — прокси
применяется ко ВСЕМ Telethon-скриптам (watch, sync). Нужен любой SOCKS5 вне РФ
(свой VPS за границей: `ss -N` / dante, или платный приватный прокси).

На VPS:

    echo 'TG_PROXY=socks5://user:pass@proxy-host:1080' >> /srv/lending_pervyi/.env.site-update-bot
    /srv/lending_pervyi/.venv/bin/pip install "python-socks[asyncio]" PySocks
    systemctl restart abhazbereg-site-update-bot
    # проверка вручную:
    cd /srv/lending_pervyi && set -a && . .env.site-update-bot && set +a \
      && .venv/bin/python scripts/watch_telegram_updates.py --limit 3

Поддерживаемые форматы: `socks5://host:port`, `socks5://user:pass@host:port`,
`socks4://…`, `http://…`.

### 3. MTProxy (если SOCKS5 недоступен)

Тоже поддержан: `TG_PROXY=mtproxy://SECRET@host:port` (секрет `dd…`/`ee…`).
Публичные MTProxy ненадёжны и часто мертвы — вариант только со своим MTProxy
на зарубежном сервере. Если заводить зарубежный сервер, проще сразу поставить
SOCKS5 (вариант 2) или вообще перенести туда бота.

### 4. Что НЕ работает

- Увеличение таймаутов (`TG_CONNECT_TIMEOUT_SECONDS` и т.п.) — соединение
  режется DPI, а не истекает.
- «Читать канал без MTProto»: web-preview t.me/s/<channel> отдаёт только
  последние посты без стабильных id альбомов и часто закрыт капчей; Bot API
  не отдаёт историю канала даже боту-админу (только новые апдейты). Для
  текущего пайплайна (сигнатуры альбомов, скачивание медиа) непригодно.

## Правила эксплуатации

- Mac и VPS не должны одновременно поллить Bot API (409 Conflict): поллер
  включён только на VPS; workflow использует только sendMessage — не конфликтует.
- Файловая сессия tg_session и TG_STRING_SESSION — секреты, в git не попадают.
- После смены пароля/сессий Telegram строковую сессию нужно перевыпустить.

## Полный автосинк в GitHub Actions (вместо ручного синка на Mac)

Тот же workflow при наличии ключей Yandex Storage сам синкает сайт: нашёл
изменения → run_auto_sync_pipeline (--snapshot-only, без Google-фильтров и
CDN-банков) → аудиты → commit → push → GitHub Pages деплоит. Секреты:

    YANDEX_S3_ACCESS_KEY_ID / YANDEX_S3_SECRET_ACCESS_KEY  (из .env.yandex.local)
    TG_BOT_TOKEN / TG_REPORT_CHAT_ID                       (уведомления)

Пока ключей нет — workflow только наблюдает и присылает «нужен ручной синк».
Фильтры из Google Sheets и пересборка CDN-банков отзывов по-прежнему запускаются
с Mac (нужны локальные креденшалы/исходники) — это редкие операции.
Ручной синк на Mac продолжает работать как раньше — конфликтов нет, пока они
не запущены одновременно.
