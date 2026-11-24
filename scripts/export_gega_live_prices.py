"""Публичный снимок только Геги из шахматки. Ключи остаются на Mac mini.

Запуск без --publish выполняет только проверку. Источник цен – gega_daily,
официальные справочники используются только для проверки категорий и тарифов.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import json
import os
import re
from pathlib import Path
import urllib.request
from zoneinfo import ZoneInfo

API = 'https://bookonline24.ru/api/v1/daily/hotel-gega/'
OBJECT_KEY = 'media/gega-live-prices/v1.json'
MAX_AGE = 7200


def load_env(path):
    for line in path.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('\"').strip("'"))


def read_json(url, headers=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=30) as response:
        return json.load(response)


def build_snapshot(rows, entities, rates, now=None):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo('Europe/Moscow')).date()
    names = [r['name'] for r in entities]
    if len(names) != 9 or len(set(names)) != 9:
        raise ValueError('Изменились категории Геги, требуется проверка соответствий')
    rate_names = {r['id']: r['name'] for r in rates}
    nights = {}
    for row in rows:
        night = row['night']
        date = datetime.strptime(night, '%Y-%m-%d').date()
        if date < today or date >= today + timedelta(days=365):
            continue
        stamp = row['checked_at'].replace('Z', '+00:00')
        # Python 3.9 на mini принимает только 3/6 знаков дробной секунды.
        stamp = re.sub(r'\.([0-9]{1,6})(?=[+-])', lambda m: '.' + m[1].ljust(6, '0'), stamp)
        checked = datetime.fromisoformat(stamp)
        if checked.tzinfo is None or not 0 <= (now - checked).total_seconds() <= MAX_AGE:
            continue
        categories = row['categories']
        if len(categories) != 9 or {c['category'] for c in categories} != set(names):
            raise ValueError('Категории шахматки не совпадают со справочником Геги')
        public = []
        for category in categories:
            count = category['available']
            if count is not None and (type(count) is not int or count < 0):
                raise ValueError('Некорректное наличие')
            tariffs = []
            for tariff in category['tariffs']:
                if tariff['rate'] not in rate_names:
                    raise ValueError('Неизвестный тариф Геги')
                price = tariff['price']
                if price is None:
                    continue
                if type(price) not in (int, float) or not 0 < price < 10000000:
                    raise ValueError('Некорректная цена')
                value = {'name': rate_names[tariff['rate']], 'price': price,
                         'meal': 'Состав питания уточнит менеджер'}
                if value not in tariffs:
                    tariffs.append(value)
            public.append({'category': category['category'], 'available': count, 'tariffs': tariffs})
        nights[night] = {'checked_at': row['checked_at'], 'categories': public}
    if not nights:
        raise ValueError('Нет свежих цен Геги, прежний снимок не перезаписываем')
    return {'version': 1, 'hotel': 'gega', 'adults': 2, 'children': 0,
            'generated_at': now.isoformat(), 'max_age_seconds': MAX_AGE, 'nights': nights}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    config = Path.home() / '.config/rental-ai'
    load_env(config / 'chessmate-cron.env')
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    rows = read_json(os.environ['NEXT_PUBLIC_SUPABASE_URL'] +
                     '/rest/v1/gega_daily?select=night,categories,checked_at&order=night',
                     {'apikey': key, 'Authorization': 'Bearer ' + key})
    snapshot = build_snapshot(rows, read_json(API + 'entities'), read_json(API + 'rates'))
    body = json.dumps(snapshot, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
    if args.publish:
        import boto3
        load_env(config / 'yandex-s3.env')
        client = boto3.client('s3', endpoint_url=os.environ['YANDEX_S3_ENDPOINT'],
                              region_name=os.environ.get('YANDEX_S3_REGION', 'ru-central1'),
                              aws_access_key_id=os.environ['YANDEX_S3_ACCESS_KEY_ID'],
                              aws_secret_access_key=os.environ['YANDEX_S3_SECRET_ACCESS_KEY'])
        client.put_object(Bucket='abhazbereg-media', Key=OBJECT_KEY, Body=body,
                          ContentType='application/json; charset=utf-8', CacheControl='no-cache, max-age=0')
    print(json.dumps({'published': args.publish, 'nights': len(snapshot['nights']), 'bytes': len(body)}))


if __name__ == '__main__':
    main()
