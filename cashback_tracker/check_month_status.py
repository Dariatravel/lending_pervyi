from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "cashback-data.json"


def current_month() -> str:
    today = date.today()
    return f"{today.year}-{today.month:02d}"


def load_data() -> dict:
    if not DATA_FILE.exists():
        return {"banks": [], "months": {}}

    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default=current_month())
    args = parser.parse_args()

    payload = load_data()
    banks = payload.get("banks", [])
    month_data = payload.get("months", {}).get(args.month, {})
    bank_payloads = month_data.get("banks", {})

    banks_with_data = 0
    category_count = 0

    for bank in banks:
        bank_id = str(bank.get("id", ""))
        categories = bank_payloads.get(bank_id, {}).get("categories", [])
        filled_categories = [item for item in categories if str(item.get("name", "")).strip()]

        if filled_categories:
            banks_with_data += 1

        category_count += len(filled_categories)

    print(
        json.dumps(
            {
                "month": args.month,
                "total_banks": len(banks),
                "banks_with_data": banks_with_data,
                "category_count": category_count,
                "has_any_data": category_count > 0,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
