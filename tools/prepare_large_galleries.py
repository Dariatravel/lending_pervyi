"""Defer offscreen media in the three large hotel galleries before publication."""
from html.parser import HTMLParser
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HOTELS = (
    "mulberri-otel-na-plyazhe-s-basseynom-i-kafe-3074",
    "villa-lyubov-vyhod-iz-otelya-srazu-na-plyazh-2716",
    "banan-i-funduk-gostevoy-dom-2849",
)
GRIDS = {"media-grid", "comment-media-grid", "comment-review-grid"}


class GalleryMarkup(HTMLParser):
    def __init__(self, page):
        super().__init__(convert_charrefs=False)
        self.lines = [0]
        for line in page.splitlines(keepends=True):
            self.lines.append(self.lines[-1] + len(line))
        self.divs = []
        self.in_noscript = False
        self.edits = []

    def handle_starttag(self, tag, attrs):
        if tag == "noscript":
            self.in_noscript = True
        if self.in_noscript:
            return
        values = dict(attrs)
        raw = self.get_starttag_text()
        if tag == "div":
            self.divs.append(bool(GRIDS.intersection(values.get("class", "").split())))
        if not any(self.divs):
            return
        if tag == "div" and "media-grid" in values.get("class", "").split() and "data-large-gallery" not in values:
            replacement = raw.replace("<div ", "<div data-large-gallery ", 1)
        elif tag == "img" and "src" in values:
            replacement = re.sub(r"(?<=\s)(srcset|src)=", r"data-gallery-\1=", raw)
            replacement += "<noscript>" + raw + "</noscript>"
        elif tag == "video" and "poster" in values:
            replacement = re.sub(r"(?<=\s)poster=", "data-gallery-poster=", raw)
        else:
            return
        line, col = self.getpos()
        self.edits.append((self.lines[line - 1] + col, raw, replacement))

    def handle_endtag(self, tag):
        if tag == "noscript":
            self.in_noscript = False
        if not self.in_noscript and tag == "div" and self.divs:
            self.divs.pop()


def prepare(page):
    parser = GalleryMarkup(page)
    parser.feed(page)
    for offset, old, new in reversed(parser.edits):
        assert page[offset:offset + len(old)] == old
        page = page[:offset] + new + page[offset + len(old):]
    if "<!-- gallery-loader-v1 -->" not in page:
        page = page.replace("</head>", '<!-- gallery-loader-v1 --><noscript><style>img[data-gallery-src]{display:none}</style></noscript></head>')
    return page.replace(
        "scripts.min.js?v=", "scripts.min.js?gallery=1&amp;v=")


if __name__ == "__main__":
    for slug in HOTELS:
        path = ROOT / "hotels" / slug / "index.html"
        page = path.read_text()
        path.write_text(prepare(page))
