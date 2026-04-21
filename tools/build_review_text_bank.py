#!/usr/bin/env python3
"""Собирает текстовую базу отзывов из скриншотов в media/reviews."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
REVIEWS_ROOT = ROOT / "media" / "reviews"
OUTPUT_PATH = REVIEWS_ROOT / "review_text_bank.json"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".heic"}

FEMALE_NAMES = [
    "Анна",
    "Марина",
    "Елена",
    "Ольга",
    "Ирина",
    "Наталья",
    "Алина",
    "Юлия",
    "Светлана",
    "Екатерина",
    "Дарья",
    "Виктория",
    "Татьяна",
    "Ксения",
    "Людмила",
    "Полина",
    "Яна",
    "Вероника",
    "Алёна",
    "София",
]

MALE_NAMES = [
    "Андрей",
    "Максим",
    "Сергей",
    "Алексей",
    "Павел",
    "Илья",
    "Михаил",
    "Егор",
    "Роман",
    "Дмитрий",
    "Никита",
    "Владимир",
    "Артём",
    "Константин",
    "Олег",
    "Игорь",
    "Денис",
    "Кирилл",
    "Виталий",
    "Юрий",
]

FEMALE_MARKERS = [
    "ехала",
    "переживала",
    "сомневалась",
    "выбирала",
    "боялась",
    "рада",
    "довольна",
    "благодарна",
    "искала",
    "хотела",
    "отдохнула",
]

MALE_MARKERS = [
    "ехал",
    "переживал",
    "сомневался",
    "выбирал",
    "опасался",
    "рад",
    "доволен",
    "благодарен",
    "искал",
    "хотел",
    "отдохнул",
]

NOISE_PATTERNS = [
    r"^\d{1,2}:\d{2}$",
    r"^(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})$",
    r"^(отзывы?|сообщения?)$",
    r"^(читать полностью|показать|скрыть)$",
    r"^(написать|ответить|переслать)$",
]


@dataclass
class RawReview:
    source_image: str
    object_slug: str
    text: str


def list_images(root: Path) -> list[Path]:
    images: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in IMAGE_EXTS:
            images.append(path)
    return sorted(images)


def build_swift_ocr_script(path: Path) -> None:
    path.write_text(
        """import Foundation
import Vision
import AppKit

struct Out: Codable {
    let path: String
    let text: String
}

func ocr(path: String) -> String {
    let url = URL(fileURLWithPath: path)
    guard let nsImage = NSImage(contentsOf: url),
          let tiffData = nsImage.tiffRepresentation,
          let bitmap = NSBitmapImageRep(data: tiffData),
          let cgImage = bitmap.cgImage else {
        return ""
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["ru-RU", "en-US"]

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    do {
        try handler.perform([request])
        let observations = request.results ?? []
        let lines = observations.compactMap { $0.topCandidates(1).first?.string }
        return lines.joined(separator: "\\n")
    } catch {
        return ""
    }
}

var inputs: [String] = []
while let line = readLine() {
    let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
    if !trimmed.isEmpty {
        inputs.append(trimmed)
    }
}

let result = inputs.map { Out(path: $0, text: ocr(path: $0)) }
let encoder = JSONEncoder()
if #available(macOS 10.13, *) {
    encoder.outputFormatting = [.withoutEscapingSlashes]
}
if let data = try? encoder.encode(result) {
    FileHandle.standardOutput.write(data)
}
""",
        encoding="utf-8",
    )


def run_ocr(images: list[Path]) -> list[dict]:
    if not images:
        return []
    script_path = Path("/tmp/ocr_reviews_batch.swift")
    build_swift_ocr_script(script_path)
    cmd = ["swift", str(script_path)]
    payload = "\n".join(str(path) for path in images) + "\n"
    completed = subprocess.run(
        cmd,
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    if completed.stderr:
        print(completed.stderr.decode("utf-8", errors="ignore"))
    return json.loads(completed.stdout.decode("utf-8"))


def is_noise_line(line: str) -> bool:
    candidate = line.strip().lower()
    if not candidate:
        return True
    for pattern in NOISE_PATTERNS:
        if re.fullmatch(pattern, candidate):
            return True
    return False


def normalize_text(raw: str) -> str:
    text = raw.replace("\u00a0", " ")
    lines = []
    for line in text.splitlines():
        clean = re.sub(r"\s+", " ", line).strip(" -•—–|")
        if not clean:
            continue
        if is_noise_line(clean):
            continue
        lines.append(clean)

    if not lines:
        return ""

    joined = " ".join(lines)
    joined = re.sub(r"https?://\S+", " ", joined)
    joined = re.sub(r"\b\d{1,2}:\d{2}\b", " ", joined)
    joined = re.sub(r"\s+", " ", joined).strip()
    if len(joined) < 35:
        return ""

    parts = re.split(r"(?<=[.!?…])\s+", joined)
    cleaned_parts = []
    for part in parts:
        candidate = part.strip(" \"'«»")
        if not candidate:
            continue
        if len(candidate) < 18:
            continue
        if not re.search(r"[А-Яа-яЁё]", candidate):
            continue
        cleaned_parts.append(candidate)

    if not cleaned_parts:
        return ""

    clipped = " ".join(cleaned_parts[:5]).strip()
    clipped = re.sub(r"\s+", " ", clipped)
    return clipped[:650].strip()


def detect_gender(text: str) -> str | None:
    lower = text.lower()
    female_hits = sum(1 for marker in FEMALE_MARKERS if marker in lower)
    male_hits = sum(1 for marker in MALE_MARKERS if marker in lower)
    if female_hits > male_hits:
        return "female"
    if male_hits > female_hits:
        return "male"
    return None


def stable_index(text: str, modulo: int) -> int:
    value = 2166136261
    for ch in text:
        value ^= ord(ch)
        value = (value * 16777619) & 0xFFFFFFFF
    return value % modulo


def assign_names(reviews: list[RawReview]) -> list[dict]:
    if not reviews:
        return []

    classified = []
    for review in reviews:
        gender = detect_gender(review.text)
        classified.append({"review": review, "gender": gender})

    total = len(classified)
    target_male = round(total * 0.2)
    target_female = total - target_male

    male_fixed = [item for item in classified if item["gender"] == "male"]
    female_fixed = [item for item in classified if item["gender"] == "female"]
    unknown = [item for item in classified if item["gender"] is None]

    male_needed = max(target_male - len(male_fixed), 0)
    female_needed = max(target_female - len(female_fixed), 0)

    unknown_sorted = sorted(unknown, key=lambda item: stable_index(item["review"].text, 10_000_000))
    male_from_unknown = unknown_sorted[:male_needed]
    female_from_unknown = unknown_sorted[male_needed : male_needed + female_needed]
    leftover_unknown = unknown_sorted[male_needed + female_needed :]
    female_from_unknown.extend(leftover_unknown)

    for item in male_from_unknown:
        item["gender"] = "male"
    for item in female_from_unknown:
        item["gender"] = "female"

    output = []
    for idx, item in enumerate(classified, start=1):
        gender = item["gender"] or "female"
        review = item["review"]
        names = FEMALE_NAMES if gender == "female" else MALE_NAMES
        name = names[stable_index(review.text + review.source_image, len(names))]
        output.append(
            {
                "id": f"ocr-{idx}",
                "name": name,
                "gender": gender,
                "text": review.text,
                "source_image": review.source_image,
                "object_slug": review.object_slug,
            }
        )

    return output


def to_raw_reviews(ocr_rows: Iterable[dict], reviews_root: Path) -> list[RawReview]:
    seen: set[str] = set()
    reviews: list[RawReview] = []
    for row in ocr_rows:
        path = Path(row.get("path", ""))
        text = normalize_text(row.get("text", ""))
        if not path or not text:
            continue
        key = re.sub(r"\s+", " ", text).strip().lower()
        if key in seen:
            continue
        seen.add(key)

        rel = path.relative_to(reviews_root)
        slug = rel.parts[0] if rel.parts else "_unknown"
        if slug == "_unmatched":
            slug = ""
        reviews.append(RawReview(source_image=str(rel), object_slug=slug, text=text))
    return reviews


def build_payload(named_reviews: list[dict]) -> dict:
    by_object: dict[str, list[dict]] = {}
    for review in named_reviews:
        slug = review.get("object_slug") or ""
        if not slug:
            continue
        by_object.setdefault(slug, []).append(review)

    female_count = sum(1 for review in named_reviews if review["gender"] == "female")
    male_count = sum(1 for review in named_reviews if review["gender"] == "male")

    return {
        "version": 1,
        "source": "ocr_screenshots_only",
        "stats": {
            "total": len(named_reviews),
            "female": female_count,
            "male": male_count,
            "female_ratio": round((female_count / len(named_reviews)) if named_reviews else 0, 4),
            "male_ratio": round((male_count / len(named_reviews)) if named_reviews else 0, 4),
            "objects_with_reviews": len(by_object),
        },
        "global": named_reviews,
        "by_object": by_object,
    }


def main() -> None:
    images = list_images(REVIEWS_ROOT)
    if not images:
        raise SystemExit("Изображения отзывов не найдены")

    print(f"Найдено изображений: {len(images)}")
    ocr_rows = run_ocr(images)
    print(f"OCR обработал: {len(ocr_rows)}")

    raw_reviews = to_raw_reviews(ocr_rows, REVIEWS_ROOT)
    print(f"Извлечено уникальных текстов: {len(raw_reviews)}")

    named_reviews = assign_names(raw_reviews)
    payload = build_payload(named_reviews)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Сохранено: {OUTPUT_PATH}")
    print(f"Статистика: {payload['stats']}")


if __name__ == "__main__":
    main()
