"""Читает рабочую карточку и сезон. Доставка только в проверенный личный чат."""
import argparse
import collections
import datetime as dt
import fcntl
import hashlib
import json
import os
import pathlib
import subprocess
from zoneinfo import ZoneInfo

import requests
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials
from card_price_audit import audit, card_rates, SEASON
from compare_price_tabs import MANUAL_TAB, SPREADSHEET_ID

HOME=pathlib.Path.home()
PRIVATE=HOME/'dev/rental-ai-data/private_сырые_не_для_облака/card-price-audit'
CONFIG=HOME/'.config/rental-ai'


def get_cards():
    sql="""SELECT COALESCE(json_agg(json_build_object('title',h.title,'channel',lower(c.source_channel),
    'post',c.source_message_id,'prices',c.site_prices)), '[]'::json)
    FROM public.hotel_cards c JOIN public.hotels h ON h.id=c.hotel_id WHERE c.source_message_id IS NOT NULL"""
    cmd=['/bin/sh','-c','. "$HOME/.config/rental-ai/supabase-db.env" && exec /opt/homebrew/opt/postgresql@17/bin/psql "$SUPABASE_DB_URL" -XAt -v ON_ERROR_STOP=1']
    cards=json.loads(subprocess.run(cmd,input=sql,text=True,capture_output=True,check=True,timeout=60).stdout)
    if not cards: raise ValueError('Источник карточек пуст')
    for c in cards:
        c['post']=int(c['post'])
        c['_rates']=card_rates(c)
    return cards


def get_rows():
    creds=Credentials.from_service_account_file(CONFIG/'google-service-account.json',scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    session=AuthorizedSession(creds)
    r=session.get(f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}',params={'ranges':f"'{MANUAL_TAB}'!A:W",'fields':'sheets(data(rowMetadata(hiddenByFilter,hiddenByUser),rowData(values(formattedValue,hyperlink,effectiveFormat(backgroundColor)))))'},timeout=60)
    r.raise_for_status()
    grid=r.json()['sheets'][0]['data'][0]
    meta=grid.get('rowMetadata',[])
    rows=[{'row':i+1,'cells':rd.get('values',[]),'hidden':any(meta[i].get(k) for k in ('hiddenByUser','hiddenByFilter')) if i<len(meta) else False} for i,rd in enumerate(grid['rowData'])]
    if len(rows)<2: raise ValueError('Таблица пуста')
    return rows


def deliver(summary,report):
    env={}
    for line in (CONFIG/'telegram.env').read_text().splitlines():
        k,_,v=line.removeprefix('export ').partition('=')
        env[k.strip()]=v.strip().strip('"').strip("'")
    base='https://api.telegram.org/bot'+env['TELEGRAM_BOT_TOKEN']
    chat=str(json.loads((CONFIG/'ads-comment-watch.json').read_text())['telegramChat'])
    if chat!='-5555716212': raise RuntimeError('Изменился ID рекламной группы')
    def call(method,**kwargs):
        try:
            response=requests.post(base+'/'+method,data={'chat_id':chat,**kwargs.pop('data',{})},timeout=45,**kwargs)
        except requests.RequestException:
            raise RuntimeError('Нет ответа Telegram: '+method) from None
        if method=='sendDocument' and response.status_code in (400,401,403,404,429) and response.json().get('ok') is False:
            (PRIVATE/'advertising.pending').unlink(missing_ok=True)
        if response.status_code!=200 or not response.json().get('ok'): raise RuntimeError('Telegram: '+method+' не подтверждён')
        return response.json()['result']
    destination=call('getChat')
    if str(destination['id'])!=chat or destination.get('title')!='Абхазберег · Реклама' or destination.get('type') not in ('group','supergroup'):
        raise RuntimeError('Не подтверждена рекламная группа')
    pending=PRIVATE/'advertising.pending'
    delivered=PRIVATE/'advertising.delivered.sha256'
    if pending.exists() and delivered.exists() and pending.read_text()==delivered.read_text():
        pending.unlink()
    if pending.exists():
        raise RuntimeError('Предыдущая доставка не подтверждена. Проверьте историю чата перед повтором.')
    pending.write_text(hashlib.sha256(report.encode()).hexdigest())
    sent=call('sendDocument',data={'caption':summary[:1024]},files={'document':('Сверка цен.txt',report.encode(),'text/plain')})
    if str(sent['chat']['id'])!=chat or not sent.get('message_id'):
        raise RuntimeError('Нет подтверждения доставки')
    print('Telegram подтвердил сообщение',sent['message_id'],destination['title'])



def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--notify',action='store_true')
    args=parser.parse_args()
    os.umask(0o077)
    PRIVATE.mkdir(exist_ok=True,parents=True)
    with (PRIVATE/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        today=dt.datetime.now(ZoneInfo('Europe/Moscow')).date()
        if today>dt.date(SEASON+1,4,30): raise ValueError('Нужна таблица нового сезона')
        records=audit(get_rows(),get_cards(),today)
        counts=collections.Counter(x[0] for x in records)
        summary='Сверка таблицы с карточками отелей\n'+'\n'.join(f'{k}: {v}' for k,v in sorted(counts.items()))
        ordered=sorted(records,key=lambda x: (x[0]=='Совпадение',x[0]))
        report=summary+'\n\n'+'\n\n'.join('\n'.join(r) for r in ordered)
        tmp=PRIVATE/'report.next';tmp.write_text(report);tmp.replace(PRIVATE/'report.txt')
        print(summary)
        digest=hashlib.sha256(report.encode()).hexdigest()
        state=PRIVATE/'advertising.delivered.sha256'
        if args.notify and (not state.exists() or state.read_text()!=digest):
            first=next((r for status in ('Расхождение цен','Наложение периодов','Пропуск дат') for r in ordered if r[0]==status),None)
            deliver(summary+('\n\n'+'\n'.join(first) if first else '')+'\nВсе исходные строки в приложении.',report)
            tmp.write_text(digest);tmp.replace(state)
            (PRIVATE/'advertising.pending').unlink()
        elif args.notify:
            print('Отчёт не изменился, повтор пропущен')


if __name__=='__main__':
    main()
