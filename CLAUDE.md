# АБХАЗБЕРЕГ — память проекта для Claude

Прочитай этот файл первым. Он заменяет историю прошлых чатов.
Владелица — Дарья: объясняй просто, по-русски, микро-шагами; команды выполняй сам.

## Архитектура (июль 2026)

- Сайт: статический, GitHub Pages, ветка `main`, домен абхазберег.рф. Пуш в main = деплой.
- Медиа: ТОЛЬКО Yandex Object Storage `storage.yandexcloud.net/abhazbereg-media/media/...`.
  Папка `media/` исключена из git. Supabase удалён навсегда (аудит должен давать нули).
- Контент: посты Telegram-каналов @abhazbooking (отели) и @abhkvartira (квартиры).
- **Автоматика в GitHub Actions** (раннеры вне РФ, т.к. MTProto с RU-хостингов заблокирован):
  - `watch-telegram.yml` — каждый час: чтение каналов (TG_STRING_SESSION в Secrets) →
    точечный синк изменённых/новых объектов → перенос медиа с подписями из комментариев →
    синк точек карты из Яндекс-конструктора (sync_objects_map_points, с 15.07.2026) →
    аудиты → commit+push → уведомление в Telegram. Ручной пересинк: Run workflow с
    inputs force_hotel_ids / force_kv_topics.
  - `post-deploy-smoke.yml` — каждые 6 ч проверяет прод (страницы, WebP, видео, запреты).
  - `lighthouse-weekly.yml` — по понедельникам: Lighthouse прод-страниц; падает и шлёт
    Telegram-уведомление, если Performance главной < 80 или отеля < 65.
  - `backfill-variants.yml` — ручная дозаливка WebP-вариантов по бакету.
  - `price-tabs-compare.yml` — по понедельникам: сверка вкладок «ЦЕНЫ АВТО» и
    «АКТУАЛЬНЫЕ ЦЕНЫ» Google-таблицы «СЕЗОН 2026» (tools/compare_price_tabs.py),
    итог в Telegram; полный отчёт — в артефактах запуска.
- VPS Timeweb удалён 13.07.2026. Mac нужен только для: фильтров из Google Sheets,
  исходников банка отзывов, перевыпуска tg_session (tools/make_tg_string_session.py).

## Железные правила

1. После правки styles.css / scripts.js / шаблонов: `python3 tools/bump_asset_version.py`
   (сам минифицирует и проставляет единый `?v=` везде + sw.js). Разнобой версий — главный
   источник багов этой недели, не допускать.
2. После любых правок: `python3 tools/audit_supabase_prod_deps.py` (нули),
   `tools/validate_catalog_snapshot.py` (issues: 0), `tools/verify_object_media.py` (OK).
   `tools/check_page_health.py` — тоже, но на машине без `media/` он честно падает
   на проверке банков (это ок в песочницах).
3. Каждый JPG в бакете обязан иметь WebP-копии -480/-960/-1440 (страницы ссылаются
   на все ширины; srcset не откатывается на src). Заливка фото — только через
   `upload_local_image_public_url` (создаёт варианты сама) или backfill.
4. Один объект = одно название: новый пост с названием существующего объекта заменяет
   старый (старый → is_active=false + redirect-страница). Реализовано в
   `materialize_object` (sync_catalog_from_telegram.py).
5. Блоки «Дополнительные обзоры» живут в `data/supplemental-blocks.json` и вставляются
   генераторами при каждой пересборке. Не редактировать страницы мимо манифеста.
6. `data/catalog-snapshot.json` не коммитить, если diff только в generated_at.
7. Секреты (tg_session, TG_STRING_SESSION, ключи Yandex, токены) — никогда в git.
8. Перед git push: `git pull --rebase origin main` (в main пушит и автосинк).
9. Таблицы Дарьи (списки объектов из Excel/Google Sheets): **скрытые строки и строки
   с заливкой в красных оттенках не учитывать** — это объекты, которые она не ведёт
   и на сайт вносить не нужно. Читать такой файл через openpyxl с проверкой
   `sheet.row_dimensions[i].hidden` и заливки ячейки, а не подряд.

## Система отзывов (для задач «по отзывам»)

Два независимых механизма:
- **Скриншотные отзывы (OCR-банк)** — распознанные тексты со скриншотов переписок:
  - Исходник: `media/reviews/review_text_bank.json` — ЕСТЬ ТОЛЬКО НА MAC (media/ вне git);
    ~906 общих отзывов + привязки к ~67 объектам.
  - На CDN раздаются нарезки: `reviews/global.json` + `reviews/<slug>/bank.json`
    (генератор: `tools/build_cdn_review_banks.py --upload`; монолит на CDN запрещён smoke'ом).
  - Рендер: scripts.js грузит global + bank объекта лениво (IntersectionObserver) и
    подставляет в блок отзывов; факты об объекте — extractObjectReviewContext.
  - Обслуживание: `tools/clean_review_text_bank.py` (чистка), 
    `tools/audit_and_fix_review_assignments.py` (перепривязка к объектам),
    `tools/organize_reviews.py` (скриншоты → manifest, тоже Mac-only исходники).
- **Случайные текстовые отзывы на главной**: `data/guest-reviews.json` (в git).

После ЛЮБОГО изменения банка на Mac: пересобрать и залить
`python3 tools/build_cdn_review_banks.py --upload --check`, затем проверить страницу
отеля в браузере (блок отзывов заполнен, консоль чистая).

## Где что лежит

- Генераторы страниц: `scripts/sync_catalog_from_telegram.py` (объекты),
  `scripts/rebuild_from_catalog_snapshot.py` (сетка/индекс/sitemap),
  `scripts/apply_telegram_supplemental_comments.py` (медиа из комментариев),
  `scripts/build_blog_posts_manifest.py` + `scripts/sync_blog_from_abhazbereg.py` (блог).
- Данные: `data/catalog-snapshot.json` (истина каталога), `data/catalog-index.json`
  (лёгкий индекс для клиента), `data/supplemental-blocks.json`, `data/blog-posts.json`.
- Диагностика и история решений: `AUTO_SYNC.md`, `deploy/TELEGRAM_CONNECTIVITY.md`.
- Задания для агентов: CURSOR_TASK.md / CODEX_TASK.md (локальные, в .gitignore).

## Известные открытые пункты

- Lighthouse: закрыт 15.07.2026 (оптимизация старта главной, коммит 04187b51):
  главная 87–95, отель 96, LCP главной ~2.9s, TBT ~0. Контроль — еженедельный
  lighthouse-weekly.yml (порог: главная ≥80, отель ≥65).
- K5 (по согласию Дарьи): чистка истории git от media/ (репозиторий ~2 ГБ) через
  git filter-repo, с бэкапом-mirror; после неё все копии переклонировать.
- K4 выполнен 13.07.2026: concept-* и код ботов `collab_bot/`, `cashback_tracker/`
  удалены из `main`; локальный архив перед удалением сохранён в Downloads.
