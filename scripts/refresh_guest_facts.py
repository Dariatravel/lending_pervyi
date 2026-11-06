"""Обновить вводные факты из сохранённых разделов Telegram без пересборки медиа."""
import json
from pathlib import Path
from bs4 import BeautifulSoup
from sync_catalog_from_telegram import select_guest_facts

ROOT = Path(__file__).resolve().parents[1]

def main():
    changed = 0
    for row in json.loads((ROOT / 'data/catalog-snapshot.json').read_text())['listings']:
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
        for article, lines in zip(grid.select('article'), groups):
            ul = article.select_one('ul')
            if ul is None:
                continue
            ul.clear()
            for line in lines:
                item = soup.new_tag('li')
                item.string = line
                ul.append(item)
            if not lines:
                article.decompose()
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
