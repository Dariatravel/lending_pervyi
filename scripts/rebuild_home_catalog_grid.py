from __future__ import annotations

from pathlib import Path

import requests

from rebuild_from_supabase import INDEX_PATH, load_env, load_hotel_card_meta, render_hotel_card, replace_catalog_block


ROOT = Path("/Users/darya_botova/Documents/New project")
ENV_PATH = ROOT / ".env.supabase.local"


def main() -> None:
    env = load_env(ENV_PATH)
    base = env["SUPABASE_URL"].rstrip("/")
    service_key = env["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}

    response = requests.get(
        f"{base}/rest/v1/listings",
        headers=headers,
        params={
            "select": "id,slug,source_kind,source_message_id,title,summary,excerpt,city,location_text,beach_text,capacity_text,page_url,telegram_url,published_at,has_video,cover_url,details,is_active,listing_media(id,media_role,sort_order,public_url,storage_path,mime_type,source_url,details)",
            "is_active": "eq.true",
            "source_kind": "eq.hotel",
            "order": "published_at.desc,id.desc",
            "limit": "2000",
        },
        timeout=120,
    )
    response.raise_for_status()
    rows = response.json() or []
    post_meta = load_hotel_card_meta()

    replace_catalog_block(
        INDEX_PATH,
        '<div class="catalog-grid" id="catalog-grid">',
        "".join(render_hotel_card(row, post_meta) for row in rows),
    )
    print(f"Обновлен блок #catalog-grid, карточек: {len(rows)}")


if __name__ == "__main__":
    main()
