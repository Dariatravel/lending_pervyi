import asyncio
import json
import re
import os
from pathlib import Path
from telethon import TelegramClient

ROOT = Path('/Users/darya_botova/Documents/New project')
TOPICS_FILE = ROOT / 'topics.json'
OUT_JSON = ROOT / 'kvartira_cards.json'
MEDIA_DIR = ROOT / 'media' / 'kvartira-cards'
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

api_id = int(os.getenv("TG_API_ID", "0"))
api_hash = os.getenv("TG_API_HASH", "")
chat = 'abhkvartira'


def slugify(s: str) -> str:
    s = s.lower().strip()
    repl = {
        'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'
    }
    s = ''.join(repl.get(ch, ch) for ch in s)
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return s[:80] or 'topic'


def excerpt(text: str, n: int = 180) -> str:
    t = re.sub(r'\s+', ' ', (text or '')).strip()
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + '…'


async def main():
    if not api_id or not api_hash:
        raise RuntimeError("Set TG_API_ID and TG_API_HASH in environment before running.")
    topics = json.loads(TOPICS_FILE.read_text(encoding='utf-8'))
    client = TelegramClient('tg_session', api_id, api_hash)
    await client.start()
    entity = await client.get_entity(chat)

    cards = []
    for i, t in enumerate(topics, 1):
        mid = t.get('top_message_id')
        if not mid:
            continue

        msg = await client.get_messages(entity, ids=mid)
        if not msg:
            continue

        title = (t.get('title') or '').strip() or f'Тема {t.get("topic_id")}'
        text = msg.raw_text or ''
        card_slug = f"{slugify(title)}-{mid}"

        image_path = ''
        has_video = bool(msg.video)

        if msg.photo:
            local = await client.download_media(msg.photo, file=str(MEDIA_DIR / f'{card_slug}.jpg'))
            if local:
                image_path = '/media/kvartira-cards/' + Path(local).name
        elif msg.document and (msg.document.mime_type or '').startswith('image/'):
            ext = '.jpg'
            mt = msg.document.mime_type or ''
            if 'png' in mt:
                ext = '.png'
            elif 'webp' in mt:
                ext = '.webp'
            local = await client.download_media(msg.document, file=str(MEDIA_DIR / f'{card_slug}{ext}'))
            if local:
                image_path = '/media/kvartira-cards/' + Path(local).name

        cards.append({
            'topic_id': t.get('topic_id'),
            'message_id': mid,
            'title': title,
            'slug': card_slug,
            'url': f'https://t.me/{chat}/{mid}',
            'excerpt': excerpt(text),
            'image': image_path,
            'has_video': has_video,
        })
        print(f'[{i}/{len(topics)}] {title}')

    OUT_JSON.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Готово: {len(cards)} карточек -> {OUT_JSON}')
    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
