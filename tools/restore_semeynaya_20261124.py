"""Восстановить одну карточку по проверенному публичному посту. По умолчанию сухой прогон."""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import urllib.request
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from sync_catalog_from_telegram import render_detail_page,build_excerpt,human_lead,parse_post
from catalog_snapshot import load_listings,save_listings

SLUG='semeynaya-kvartira-2k-1104'
URL='https://t.me/abhkvartira/1104'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    hidden=json.loads((ROOT/'tools/hidden_listings.json').read_text())
    if SLUG in hidden:raise RuntimeError('Объект скрыт вручную, восстановление остановлено')
    rows=load_listings();old=next(r for r in rows if r['slug']==SLUG)
    if any(r.get('is_active') and r['source_kind']=='kvartira' and (r.get('source_message_id')==1104 or r.get('source_topic_id')==1103) for r in rows if r['slug']!=SLUG):
        raise RuntimeError('Найдена другая активная карточка того же источника')
    page=urllib.request.urlopen(URL+'?embed=1&mode=tme',timeout=30).read().decode()
    widget=BeautifulSoup(page,'html.parser').select_one('.tgme_widget_message_text')
    if not widget:raise RuntimeError('Публичный источник не подтверждён')
    for br in widget.select('br'):br.replace_with('\n')
    text=widget.get_text()
    parsed=parse_post(text)
    if ('семейная' not in re.sub(r'\s+','',parsed.get('title','').lower()) or
        '49/2' not in parsed.get('location','') or 'Гагра' not in parsed.get('location','')):
        raise RuntimeError('Название и адрес источника не совпали')
    row=deepcopy(old)
    row.update(title=parsed['title'],summary=human_lead(parsed),excerpt=build_excerpt(parsed),is_active=True,
               location_text=parsed['location'],beach_text=parsed.get('beach',''),capacity_text=parsed.get('capacity',''))
    row['details'].update(sections=parsed['sections'],prices=parsed['prices'],lead=row['summary'])
    relative=Path('kvartira')/SLUG/'index.html'
    row['details']['page_path']=relative.as_posix()
    media=[{'kind':'video' if str(m.get('mime_type','')).startswith('video/') else 'photo',
            'source_url':m['public_url'],'public_url':m['public_url']}
           for m in row['media'] if m.get('media_role')!='card']
    html=render_detail_page('kvartira',SLUG,URL,row['published_at'],parsed,media,f'/kvartira/{SLUG}/')
    print(json.dumps({'apply':args.apply,'slug':SLUG,'previous_active':old['is_active'],
                     'title':row['title'],'media':len(row['media']),'price_lines':len(parsed['prices'])},ensure_ascii=False))
    if args.apply:
        target=ROOT/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(html)
        rows[rows.index(old)]=row;save_listings(rows,source='restore-public-post-20261124')


if __name__=='__main__':main()
