#!/usr/bin/env python3
"""One-off cleanup: VK https, stray U+FE0F after punctuation/beach line, &quot; pairs -> «»."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fix_text(text: str) -> str:
    text = text.replace("http://vk.cc/cQQnBn", "https://vk.cc/cQQnBn")

    VS = "\ufe0f"
    text = re.sub(r"\.\s*" + VS + r"\s+", ". ", text)
    text = re.sub(r"\.\s*" + VS + r"(\d)", r". \1", text)
    text = re.sub(r"(🏖️\s*)" + VS + r"\s+", r"\1", text)

    text = text.replace("<span>" + VS + " 0 ", "<span>0 ")

    text = re.sub(r"&quot;([^&]*?)&quot;", r"«\1»", text)

    return text


def main() -> None:
    updated = 0
    for path in sorted(ROOT.rglob("*.html")):
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as e:
            print("skip", path, e, file=sys.stderr)
            continue
        fixed = fix_text(raw)
        if fixed != raw:
            path.write_text(fixed, encoding="utf-8")
            updated += 1
    print(f"updated {updated} html files")


if __name__ == "__main__":
    main()
