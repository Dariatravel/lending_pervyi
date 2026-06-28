#!/usr/bin/env python3
"""Check/apply updates for site object map points from Yandex Map Constructor."""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import build_objects_map_points  # noqa: E402

POINTS_PATH = ROOT / "data" / "objects-map-points.json"
REPORT_PATH = ROOT / "output" / "objects-map-sync-report.txt"
SUMMARY_PATH = ROOT / "output" / "objects-map-sync-summary.json"


@dataclass
class MapDiff:
    added: list[dict[str, Any]]
    removed: list[dict[str, Any]]
    moved: list[dict[str, Any]]
    changed: list[dict[str, Any]]

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.moved or self.changed)


def load_current_payload() -> dict[str, Any]:
    if not POINTS_PATH.exists():
        return {"points": [], "stats": {}}
    return json.loads(POINTS_PATH.read_text(encoding="utf-8"))


def point_key(point: dict[str, Any]) -> str:
    return str(point.get("url") or point.get("title") or "").strip()


def comparable_point(point: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": point.get("title") or "",
        "address": point.get("address") or "",
        "lat": round(float(point.get("lat") or 0), 6),
        "lon": round(float(point.get("lon") or 0), 6),
        "url": point.get("url") or "",
        "cityKey": point.get("cityKey") or "",
    }


def distance_meters(old: dict[str, Any], new: dict[str, Any]) -> float:
    lat1 = math.radians(float(old.get("lat") or 0))
    lat2 = math.radians(float(new.get("lat") or 0))
    dlat = lat2 - lat1
    dlon = math.radians(float(new.get("lon") or 0) - float(old.get("lon") or 0))
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compare_points(current: dict[str, Any], fresh: dict[str, Any]) -> MapDiff:
    current_by_key = {
        point_key(point): comparable_point(point)
        for point in current.get("points") or []
        if point_key(point)
    }
    fresh_by_key = {
        point_key(point): comparable_point(point)
        for point in fresh.get("points") or []
        if point_key(point)
    }
    added = [fresh_by_key[key] for key in sorted(set(fresh_by_key) - set(current_by_key))]
    removed = [current_by_key[key] for key in sorted(set(current_by_key) - set(fresh_by_key))]
    moved: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []

    for key in sorted(set(current_by_key) & set(fresh_by_key)):
        old = current_by_key[key]
        new = fresh_by_key[key]
        dist = distance_meters(old, new)
        if dist >= 5:
            moved.append(
                {
                    "title": new["title"],
                    "url": new["url"],
                    "from": {"lat": old["lat"], "lon": old["lon"]},
                    "to": {"lat": new["lat"], "lon": new["lon"]},
                    "meters": round(dist),
                }
            )
            continue
        old_meta = {k: old[k] for k in ("title", "address", "cityKey")}
        new_meta = {k: new[k] for k in ("title", "address", "cityKey")}
        if old_meta != new_meta:
            changed.append({"before": old, "after": new})

    return MapDiff(added=added, removed=removed, moved=moved, changed=changed)


def format_point(point: dict[str, Any]) -> str:
    title = point.get("title") or point.get("url") or "точка"
    city = point.get("cityKey") or "без города"
    return f"{title} ({city})"


def render_report(current: dict[str, Any], fresh: dict[str, Any], diff: MapDiff, *, applied: bool) -> str:
    current_count = len(current.get("points") or [])
    fresh_count = len(fresh.get("points") or [])
    stats = fresh.get("stats") or {}
    lines = [
        "Проверка карты завершена.",
        f"Сейчас на сайте: {current_count} точек.",
        f"Актуально по интерактивной карте: {fresh_count} точек.",
        f"Метки конструктора: {stats.get('placemarks_total', 0)} всего, {stats.get('placemarks_unique', 0)} уникальных.",
        f"Без метки в конструкторе: {stats.get('skipped_without_constructor', 0)}.",
    ]
    if not diff.has_changes:
        lines.append("")
        lines.append("Изменений в точках карты нет.")
    else:
        lines.append("")
        lines.append("Найдены изменения:")
        lines.append(f"- новых точек: {len(diff.added)}")
        lines.append(f"- удалённых точек: {len(diff.removed)}")
        lines.append(f"- перемещённых точек: {len(diff.moved)}")
        lines.append(f"- изменений подписи/адреса: {len(diff.changed)}")
        if diff.added:
            lines.append("")
            lines.append("Новые точки:")
            lines.extend(f"- {format_point(point)}" for point in diff.added[:12])
        if diff.removed:
            lines.append("")
            lines.append("Удалённые точки:")
            lines.extend(f"- {format_point(point)}" for point in diff.removed[:12])
        if diff.moved:
            lines.append("")
            lines.append("Перемещённые точки:")
            for point in diff.moved[:12]:
                lines.append(f"- {point['title']}: примерно {point['meters']} м")
        lines.append("")
        lines.append("Что делать: нажмите «Обновить карту», чтобы применить изменения на сайте.")

    if applied:
        lines.append("")
        lines.append("Изменения карты применены к data/objects-map-points.json.")
    return "\n".join(lines) + "\n"


def save_outputs(report: str, current: dict[str, Any], fresh: dict[str, Any], diff: MapDiff, *, applied: bool) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "applied": applied,
        "current_points": len(current.get("points") or []),
        "fresh_points": len(fresh.get("points") or []),
        "changes": {
            "added": diff.added,
            "removed": diff.removed,
            "moved": diff.moved,
            "changed": diff.changed,
        },
        "has_changes": diff.has_changes,
    }
    SUMMARY_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверить или обновить точки объектов на карте.")
    parser.add_argument("--apply", action="store_true", help="Записать обновлённые точки в data/objects-map-points.json.")
    parser.add_argument("--no-write", action="store_true", help="Только проверить и вывести отчёт, не записывать output-файлы.")
    args = parser.parse_args()

    current = load_current_payload()
    fresh = build_objects_map_points.build_points()
    diff = compare_points(current, fresh)

    applied = False
    if args.apply and diff.has_changes:
        POINTS_PATH.write_text(json.dumps(fresh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        applied = True

    report = render_report(current, fresh, diff, applied=applied)
    if not args.no_write:
        save_outputs(report, current, fresh, diff, applied=applied)
    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
