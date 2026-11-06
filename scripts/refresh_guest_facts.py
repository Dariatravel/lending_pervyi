"""Обновить вводные факты из сохранённых разделов Telegram без пересборки медиа."""
import json
from pathlib import Path
from bs4 import BeautifulSoup
from sync_catalog_from_telegram import select_guest_facts

ROOT = Path(__file__).resolve().parents[1]

def main():
    changed = 0
    for row in json.loads((ROOT / 'data/catalog-snapshot.json').read_text())['listings']:
        if row.get('is_active') is False:
            continue
        folder = 'kvartira' if row['source_kind'] == 'kvartira' else 'hotels'
        path = ROOT / folder / row['slug'] / 'index.html'
        if not path.exists():
            continue
        original = path.read_text()
        soup = BeautifulSoup(original, 'html.parser')
        grid = soup.select_one('.benefit-grid')
        if not grid:
            continue
        groups = select_guest_facts(row.get('details', {}).get('sections', []))
        grid.clear()
        for title, lines in zip(('Почему выбирают', 'Важно для гостя'), groups):
            if not lines:
                continue
            article = soup.new_tag('article')
            heading = soup.new_tag('strong')
            heading.string = title
            article.append(heading)
            ul = soup.new_tag('ul')
            article.append(ul)
            grid.append(article)
            for line in lines:
                item = soup.new_tag('li')
                item.string = line
                ul.append(item)
        # Меняем только блок, сохраняя остальную разметку страницы.
        start = original.find('<div class="benefit-grid">')
        end = original.find('</div>', start) + len('</div>')
        if start >= 0:
            updated = original[:start] + str(grid) + original[end:]
            if updated != original:
                path.write_text(updated)
                changed += 1
    print(f'Обновлено страниц: {changed}')

if __name__ == '__main__':
    main()
