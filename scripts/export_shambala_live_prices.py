"""Передача цен только Шамбалы из шахматки в публичный JSON. Без --publish – сухой прогон."""
from __future__ import annotations

import argparse
from copy import deepcopy
import gzip
import json
import os
from pathlib import Path
from urllib.parse import urlencode

from export_gega_live_prices import build_snapshot as validate_snapshot, load_env, read_json

ROOMS = {
    '390746': 'Стандарт', '390747': 'Комфорт', '390749': 'Делюкс',
    '390748': 'Полулюкс', '390750': 'Люкс', '390751': 'Семейный люкс с террасой',
    '390752': 'А-фрейм', '390753': 'Барнхаус', '394428': 'Семейный люкс с крытой террасой',
}
# Только однозначные официальные названия. Базовый тариф не считаем питанием по догадке.
MEALS = {
    '998779': ('Раннее бронирование с завтраком', 'Завтрак включён'),
    '998780': ('Длительное проживание с завтраком', 'Завтрак включён'),
    '998781': ('Горящее предложение с завтраком', 'Завтрак включён'),
    '998782': ('Длительное проживание без завтрака', 'Без завтрака'),
    '998783': ('Раннее бронирование без питания', 'Без питания'),
    '998784': ('Горящее предложение без питания', 'Без питания'),
    '998787': ('Базовый с завтраком', 'Завтрак включён'),
}


def build_snapshot(rows, hotel, now=None):
    if hotel['code'] != '64223' or {r['code']: r['name'] for r in hotel['room_types']} != ROOMS:
        raise ValueError('Изменились категории Шамбалы, требуется проверка')
    if any(r.get('max_adult_occupancy', 0) < 2 for r in hotel['room_types']):
        raise ValueError('Изменилось размещение Шамбалы')
    rates, meals = [], {}
    for rate in hotel['rate_plans']:
        name = rate['name']
        if name in meals:
            raise ValueError('Неоднозначные названия тарифов Шамбалы')
        verified = MEALS.get(rate['code'])
        if verified and verified[0] != name:
            raise ValueError('Изменились условия питания Шамбалы')
        meals[name] = verified[1] if verified else 'Питание уточняется'
        rates.append({'id': name, 'name': name})
    # Общий валидатор проверяет давность, суммы, точное совпадение всех 9 категорий.
    snapshot = validate_snapshot(deepcopy(rows), hotel['room_types'], rates, now)
    snapshot['hotel'] = 'shambala'
    for night in snapshot['nights'].values():
        for category in night['categories']:
            for tariff in category['tariffs']:
                tariff['meal'] = meals[tariff['name']]
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    config = Path.home() / '.config/rental-ai'
    load_env(config / 'chessmate-cron.env')
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    rows = read_json(os.environ['NEXT_PUBLIC_SUPABASE_URL'] +
                     '/rest/v1/shambala_daily?select=night,categories,checked_at&order=night',
                     {'apikey': key, 'Authorization': 'Bearer ' + key})
    hotel = read_json('https://ab-ibe.tlintegration.com/ApiWebDistribution/BookingForm/hotel_info?' +
                      urlencode({'hotels[0].code': '64223', 'language': 'ru-ru'}))['hotels'][0]
    snapshot = build_snapshot(rows, hotel)
    body = json.dumps(snapshot, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
    if args.publish:
        import boto3
        load_env(config / 'yandex-s3.env')
        client = boto3.client('s3', endpoint_url=os.environ['YANDEX_S3_ENDPOINT'],
                              region_name=os.environ.get('YANDEX_S3_REGION', 'ru-central1'),
                              aws_access_key_id=os.environ['YANDEX_S3_ACCESS_KEY_ID'],
                              aws_secret_access_key=os.environ['YANDEX_S3_SECRET_ACCESS_KEY'])
        client.put_object(Bucket='abhazbereg-media', Key='media/shambala-live-prices/v1.json',
                          Body=gzip.compress(body, mtime=0), ContentEncoding='gzip',
                          ContentType='application/json; charset=utf-8', CacheControl='no-cache, max-age=0')
    print(json.dumps({'published': args.publish, 'nights': len(snapshot['nights']), 'bytes': len(body)}))


if __name__ == '__main__':
    main()
