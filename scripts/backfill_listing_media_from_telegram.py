#!/usr/bin/env python3
"""
Дозагрузка медиа для объектов, у которых в Supabase нет строк listing_media.

Сценарий: объект попал в базу через backfill/ручную вставку без sync_catalog_from_telegram —
карточки на главной без картинок (URL /media/... отсутствует в деплое).

Что делает:
1. Находит активные объекты без listing_media (опционально: только указанный kind).
2. Запускает точечный sync_catalog_from_telegram.py с TARGET_HOTEL_SOURCE_IDS / TARGET_KV_TOPIC_IDS.

Запуск из корня репозитория (нужны .env.supabase.local, tg_session):

  python3 scripts/backfill_listing_media_from_telegram.py
  python3 scripts/backfill_listing_media_from_telegram.py --dry-run

Квартиры: topic_id в базе = source_topic_id. Отели: source_message_id.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / '.env.supabase.local'


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        data[k.strip()] = v.strip()
    return data


def fetch_json(url: str, headers: dict[str, str], params: dict[str, str]) -> list | dict:
    r = requests.get(url, headers=headers, params=params, timeout=120)
    r.raise_for_status()
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true', help='Только напечатать ID, не запускать sync.')
    ap.add_argument('--kind', choices=('hotel', 'kvartira', 'all'), default='all')
    ap.add_argument(
        '--chunk',
        type=int,
        default=35,
        metavar='N',
        help='Сколько message_id / topic_id за один вызов sync (меньше нагрузка на Telegram).',
    )
    args = ap.parse_args()

    env = load_env(ENV_PATH)
    sb_url = env.get('SUPABASE_URL', '').rstrip('/')
    key = env.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not sb_url or not key:
        print('Нужны SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в .env.supabase.local', file=sys.stderr)
        return 1

    headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
    base = f'{sb_url}/rest/v1/listings'

    rows_by_kind: list[dict] = []
    if args.kind in ('hotel', 'all'):
        rows_by_kind.extend(
            fetch_json(
                base,
                headers,
                {'select': 'id,slug,source_kind,source_message_id,source_topic_id', 'is_active': 'eq.true', 'source_kind': 'eq.hotel', 'limit': '5000'},
            )
        )
    if args.kind in ('kvartira', 'all'):
        rows_by_kind.extend(
            fetch_json(
                base,
                headers,
                {'select': 'id,slug,source_kind,source_message_id,source_topic_id', 'is_active': 'eq.true', 'source_kind': 'eq.kvartira', 'limit': '5000'},
            )
        )

    lm_index = fetch_json(f'{sb_url}/rest/v1/listing_media', headers, {'select': 'listing_id', 'limit': '100000'})
    have_media = {int(row['listing_id']) for row in lm_index if row.get('listing_id')}

    hotel_ids_without_media: list[int] = []
    kv_topic_ids_without_media: list[int] = []

    for row in rows_by_kind:
        lid = int(row['id'])
        if lid in have_media:
            continue
        kind = row.get('source_kind')
        if kind == 'hotel':
            mid = int(row.get('source_message_id') or 0)
            if mid > 0:
                hotel_ids_without_media.append(mid)
        elif kind == 'kvartira':
            tid = row.get('source_topic_id')
            if tid is not None:
                kv_topic_ids_without_media.append(int(tid))

    hotel_ids_without_media = sorted(set(hotel_ids_without_media))
    kv_topic_ids_without_media = sorted(set(kv_topic_ids_without_media))

    print(f'Без listing_media: отели (message id)={len(hotel_ids_without_media)}, квартиры (topic id)={len(kv_topic_ids_without_media)}')
    if hotel_ids_without_media:
        print('Отели:', ','.join(str(x) for x in hotel_ids_without_media[:80]), ('…' if len(hotel_ids_without_media) > 80 else ''))
    if kv_topic_ids_without_media:
        print('Квартиры topics:', ','.join(str(x) for x in kv_topic_ids_without_media[:80]), ('…' if len(kv_topic_ids_without_media) > 80 else ''))

    if args.dry_run:
        print('Dry-run — sync не запускался.')
        return 0

    if not hotel_ids_without_media and not kv_topic_ids_without_media:
        print('Не обрабатываем — нечего дозаполнять.')
        return 0

    # Точечный sync: по одному kind за вызов, чтобы логика main() отключила второй канал.
    tg_session = os.environ.get('TG_SESSION', str(ROOT / 'tg_session'))
    python = sys.executable
    sync_py = ROOT / 'scripts' / 'sync_catalog_from_telegram.py'
    rc = 0

    def run_segment(target_hotels: bool, ids_csv: str) -> int:
        e = dict(os.environ)
        e['TG_SESSION'] = tg_session
        # sync_catalog_from_telegram: один канал включается, если второй TARGET пустой.
        if target_hotels:
            e['TARGET_HOTEL_SOURCE_IDS'] = ids_csv
            e['TARGET_KV_TOPIC_IDS'] = ''
        else:
            e['TARGET_KV_TOPIC_IDS'] = ids_csv
            e['TARGET_HOTEL_SOURCE_IDS'] = ''
        print(f"Запуск sync (hotels={'да' if target_hotels else 'нет'}): {ids_csv[:200]}{'…' if len(ids_csv) > 200 else ''}")
        proc = subprocess.run([python, str(sync_py)], cwd=str(ROOT), env=e)
        return int(proc.returncode)

    # sync main() выбирает канал только по TARGET_* если задан один — применяется env из sync файла через os.getenv
    def chunked(seq: list[int], size: int) -> list[list[int]]:
        if size <= 0:
            return [seq]
        return [seq[i : i + size] for i in range(0, len(seq), size)]

    for batch in chunked(hotel_ids_without_media, args.chunk):
        csv_h = ','.join(str(x) for x in batch)
        step = run_segment(True, csv_h)
        rc = max(rc, step)
        if step != 0:
            print(f'[warn] Пакет отелей завершился с кодом {step}: {csv_h[:80]}…', file=sys.stderr)

    for batch in chunked(kv_topic_ids_without_media, args.chunk):
        csv_k = ','.join(str(x) for x in batch)
        rc = max(rc, run_segment(False, csv_k))

    print('\nПосле успешного sync: выполните `python3 scripts/rebuild_from_supabase.py`, чтобы главная подтянула public_url карточек.')
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
