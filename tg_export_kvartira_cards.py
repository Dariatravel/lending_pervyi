import asyncio
import json
import re
import os
import html
import urllib.request
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


def fetch_og_image_url(message_id: int) -> str:
    url = f'https://t.me/s/{chat}/{message_id}'
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 Chrome/122 Safari/537.36'},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        page = resp.read().decode('utf-8', errors='ignore')
    m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', page, flags=re.IGNORECASE)
    if not m:
        return ''
    return html.unescape(m.group(1))


def download_remote_image(url: str, dst: Path) -> bool:
    if not url:
        return False
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 Chrome/122 Safari/537.36'},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    if not data:
        return False
    dst.write_bytes(data)
    return True


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

        # Fallback: for many forum topics the top message has no attached photo,
        # but Telegram public page still exposes a post cover in og:image.
        if not image_path:
            try:
                og_url = fetch_og_image_url(mid)
                dst = MEDIA_DIR / f'{card_slug}-cover.jpg'
                if download_remote_image(og_url, dst):
                    image_path = '/media/kvartira-cards/' + dst.name
            except Exception:
                pass

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
