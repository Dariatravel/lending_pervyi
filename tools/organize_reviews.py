#!/usr/bin/env python3
import hashlib
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEWS_DIR = ROOT / "media" / "reviews"
PAGES_FILE = ROOT / "output" / "current_pages.json"
MANIFEST_FILE = REVIEWS_DIR / "manifest.json"
UNMATCHED_DIR = REVIEWS_DIR / "_unmatched"
YANDEX_MEDIA_BASE = "https://storage.yandexcloud.net/abhazbereg-media/media"

CYR_TO_LAT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

STOP_WORDS = {
    "otzyvy",
    "otzyv",
    "reviews",
    "review",
    "vse",
    "jpg",
    "jpeg",
    "png",
    "webp",
    "photo",
    "screenshot",
    "img",
    "domiki",
    "domik",
    "otel",
    "gostevoy",
    "dom",
    "apartamenty",
    "apartament",
    "mini",
    "kompleks",
    "nomera",
    "nomer",
    "kottedzhi",
    "kottedzh",
    "basseynom",
    "pitaniem",
    "plyazhe",
    "more",
    "gostinitsa",
    "vidovoy",
    "butik",
    "teplym",
    "pervoy",
    "linii",
    "vyhod",
    "srazu",
    "zavtrakami",
    "gorah",
    "abhazii",
    "abhaziya",
    "otelya",
    "sosnovogo",
    "derevyannye",
    "park",
    "house",
    "guest",
    "inn",
    "resort",
    "family",
    "u",
    "na",
    "v",
    "i",
    "s",
    "novyy",
    "novaya",
    "novoe",
    "tsandripsh",
    "gagra",
    "alahadzy",
    "tsitrus",
    "pitsunda",
    "ldzaa",
    "gudauta",
    "novyy",
    "afon",
    "suhum",
    "sinop",
    "non",
    "grata",
    "anhua",
}

MANUAL_ALIASES = {
    "fazenda": {
        "fazenda-kottedzhi",
        "fazenda-otel-s-basseynom-i-pitaniem-3190",
    },
    "grant": {
        "grant-apartamenty-2801",
        "grant-kompleks-domikov-s-zavtrakami-2811",
        "grant-otel-nomera-2820",
    },
    "rivera": {
        "rivera-domiki-na-plyazhe-2966",
        "rivera-gostinitsa-vidovaya-2706",
    },
    "amor": {
        "amor-apartamenty",
        "amor-domiki-gagra",
    },
    "sun amra": {"san-amra-novyy-otel-na-plyazhe-ldzaa-2631"},
    "san amra": {"san-amra-novyy-otel-na-plyazhe-ldzaa-2631"},
    "sun pino": {"san-pino-domiki-derevyannye-s-basseynom-3005"},
    "san pino": {"san-pino-domiki-derevyannye-s-basseynom-3005"},
    "villa leona": {"villa-leona-otel-s-basseynom-pitaniem-i-sobs-2755"},
    "villa lyubov": {"villa-lyubov-vyhod-iz-otelya-srazu-na-plyazh-2716"},
    "lavanda": {"lavanda-villa-s-basseynom-2774"},
    "lnd": {"lnd-gostevoy-dom-v-sinope-3687"},
    "sinop haus": {"sinop-haus-domiki-3748"},
    "sinop houses": {"sinop-haus-domiki-3748"},
    "v sinope": {"v-sinope-domiki"},
    "at the sea": {"u-morya-domiki-3200"},
    "castle": {"kastl-otel-s-teplym-basseynom-i-vidom-na-mor-2859"},
    "kastl": {"kastl-otel-s-teplym-basseynom-i-vidom-na-mor-2859"},
    "fusion": {"fyuzhn-tri-domika"},
    "fyuzhn": {"fyuzhn-tri-domika"},
    "eco haus pitiunt": {"eko-haus-pitiunt-domiki-s-basseynom-3545"},
    "eko haus pitiunt": {"eko-haus-pitiunt-domiki-s-basseynom-3545"},
    "pitiunt": {"eko-haus-pitiunt-domiki-s-basseynom-3545"},
    "green village": {"grin-villadzh-domiki-3633"},
    "green house": {"grin-haus-domiki"},
    "grin hauz": {"grin-haus-domiki"},
    "seaside": {"sisayd-domiki-3409"},
    "sea side": {"sisayd-domiki-3409"},
    "sisayd": {"sisayd-domiki-3409"},
    "white horse": {"belaya-loshad-glemping-s-basseynom-3650"},
    "belaya loshad": {"belaya-loshad-glemping-s-basseynom-3650"},
    "slavitsa": {"miraslava-mini-otel-3143"},
    "slavica": {"miraslava-mini-otel-3143"},
}

ALLOWED_SHARED_ALIASES = {"fazenda", "grant", "rivera", "amor"}


def transliterate(text: str) -> str:
    return "".join(CYR_TO_LAT.get(char, char) for char in text.lower())


def normalize_text(text: str) -> str:
    text = transliterate(text)
    text = text.replace("&quot;", " ")
    text = re.sub(r"\.[a-z0-9]+$", " ", text)
    text = re.sub(r"__.*$", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def cleaned_phrase(text: str) -> str:
    normalized = normalize_text(text)
    tokens = []
    for token in normalized.split():
        if token.isdigit() or token in STOP_WORDS:
            continue
        tokens.append(token)
    return " ".join(tokens)


def load_pages() -> list[dict]:
    return json.loads(PAGES_FILE.read_text(encoding="utf-8"))


def build_alias_map(pages: list[dict]) -> dict[str, set[str]]:
    aliases: dict[str, set[str]] = defaultdict(set)

    for page in pages:
        slug = page["slug"]
        sources = {
            cleaned_phrase(page["title"]),
            cleaned_phrase(slug.replace("-", " ")),
        }

        for source in sources:
            if not source:
                continue

            tokens = source.split()
            aliases[slug].add(source)
            for size in (1, 2, 3):
                if len(tokens) >= size:
                    aliases[slug].add(" ".join(tokens[:size]))
            for token in tokens:
                if len(token) >= 5:
                    aliases[slug].add(token)

    for alias, slugs in MANUAL_ALIASES.items():
        for slug in slugs:
            aliases[slug].add(alias)

    return aliases


def best_targets(file_name: str, alias_lookup: dict[str, set[str]]) -> set[str]:
    haystack = f" {cleaned_phrase(file_name)} "
    matches = []

    for alias, slugs in alias_lookup.items():
        if not alias:
            continue
        if len(slugs) > 1 and alias not in ALLOWED_SHARED_ALIASES:
            continue

        needle = f" {alias} "
        if needle in haystack:
            matches.append((len(alias.split()), len(alias), alias, slugs))

    if not matches:
        return set()

    matches.sort(reverse=True)
    return set(matches[0][3])


def file_hash(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def existing_hashes(folder: Path) -> dict[str, Path]:
    hashes: dict[str, Path] = {}
    if not folder.exists():
        return hashes

    for item in folder.iterdir():
        if item.is_file():
            hashes[file_hash(item)] = item
    return hashes


def unique_destination(folder: Path, file_name: str, digest: str) -> Path:
    candidate = folder / file_name
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    return folder / f"{stem}-{digest[:8]}{suffix}"


def organize_reviews() -> dict:
    pages = load_pages()
    alias_map = build_alias_map(pages)

    alias_lookup: dict[str, set[str]] = defaultdict(set)
    for slug, aliases in alias_map.items():
        for alias in aliases:
            if len(alias) >= 4:
                alias_lookup[alias].add(slug)

    folder_hash_cache: dict[Path, dict[str, Path]] = {}
    summary = {
        "moved": 0,
        "copied": 0,
        "deduped": 0,
        "unmatched": 0,
        "folders": defaultdict(int),
    }

    root_files = [path for path in REVIEWS_DIR.iterdir() if path.is_file() and path.name != MANIFEST_FILE.name]

    for source_file in root_files:
        targets = best_targets(source_file.name, alias_lookup)
        if not targets:
            targets = {"_unmatched"}
            summary["unmatched"] += 1

        digest = file_hash(source_file)
        target_paths = []

        for slug in sorted(targets):
            folder = UNMATCHED_DIR if slug == "_unmatched" else REVIEWS_DIR / slug
            folder.mkdir(parents=True, exist_ok=True)
            if folder not in folder_hash_cache:
                folder_hash_cache[folder] = existing_hashes(folder)

            if digest in folder_hash_cache[folder]:
                summary["deduped"] += 1
                continue

            destination = unique_destination(folder, source_file.name, digest)
            target_paths.append(destination)
            folder_hash_cache[folder][digest] = destination
            summary["folders"][folder.name] += 1

        if not target_paths:
            source_file.unlink()
            continue

        first_destination = target_paths[0]
        source_file.replace(first_destination)
        summary["moved"] += 1

        for extra_destination in target_paths[1:]:
            shutil.copy2(first_destination, extra_destination)
            summary["copied"] += 1

    manifest = {}
    for folder in sorted(REVIEWS_DIR.iterdir(), key=lambda item: item.name):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        files = sorted([item for item in folder.iterdir() if item.is_file()])
        if not files:
            continue
        manifest[folder.name] = [f"{YANDEX_MEDIA_BASE}/reviews/{folder.name}/{item.name}" for item in files]

    MANIFEST_FILE.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return summary | {"manifest_entries": len(manifest)}


if __name__ == "__main__":
    result = organize_reviews()
    print(json.dumps(result, ensure_ascii=False, indent=2))
