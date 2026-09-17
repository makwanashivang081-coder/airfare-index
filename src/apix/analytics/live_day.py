"""Daily collect rollup for the Live tab (all airlines — live + sample)."""

from __future__ import annotations

import json
from datetime import date

from sqlalchemy.orm import Session

from apix.common.config import settings
from apix.common.logging import backend_root
from apix.db.models import AirlineRow, FareObservationRow, RawObservationRow, SourceRow


def _inner_payload(raw: RawObservationRow | None) -> dict:
    if raw is None:
        return {}
    try:
        blob = json.loads(raw.payload_json or "{}")
    except json.JSONDecodeError:
        return {}
    if isinstance(blob, dict) and isinstance(blob.get("payload"), dict):
        return blob["payload"]
    return blob if isinstance(blob, dict) else {}


def is_live_payload(inner: dict) -> bool:
    """True only for real live pages — not airline rows filled via Google Flights proxy."""
    if str(inner.get("collection") or "").upper() != "LIVE":
        return False
    # Proxy under an airline source_id must not count as that airline's "live".
    if inner.get("market_proxy"):
        return False
    return True


def _load_day_summary() -> dict | None:
    path = backend_root() / "data" / "live" / "day_summary.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _schedule() -> dict:
    cfg = settings()
    collect = cfg.get("collect") if isinstance(cfg.get("collect"), dict) else {}
    return {
        "local_time": str(collect.get("local_time") or "02:00"),
        "timezone": str(collect.get("timezone") or "Asia/Kolkata"),
        "label": str(collect.get("label") or "Every day at 2:00 AM India time"),
        "airlines": str(collect.get("airlines") or "SG, 6E, AI, QP (+ MMT market)"),
    }


def live_day_payload(session: Session, day: date) -> dict:
    rows = (
        session.query(FareObservationRow)
        .filter(
            FareObservationRow.collected_on == day,
            FareObservationRow.advance_purchase_days == 21,
        )
        .all()
    )
    sources = {row.id: row for row in session.query(SourceRow).all()}
    airlines = {row.code: row.name for row in session.query(AirlineRow).all()}
    raw_ids = {r.raw_id for r in rows}
    raws = {
        row.id: row
        for row in session.query(RawObservationRow).filter(RawObservationRow.id.in_(raw_ids)).all()
    } if raw_ids else {}

    quotes: list[dict] = []
    live_n = 0
    sample_n = 0
    by_source: dict[str, dict] = {}
    by_route: dict[str, dict] = {}

    for row in rows:
        src = sources.get(row.source_id)
        inner = _inner_payload(raws.get(row.raw_id))
        live = is_live_payload(inner)
        mode = "live" if live else "sample"
        if live:
            live_n += 1
        else:
            sample_n += 1

        key = row.source_id
        bucket = by_source.setdefault(
            key,
            {
                "source_id": key,
                "source_name": src.name if src else key,
                "live": 0,
                "sample": 0,
                "can_enter_cpi": bool(src.can_enter_cpi) if src else False,
            },
        )
        bucket[mode] += 1

        route = f"{row.origin}-{row.destination}"
        route_bucket = by_route.setdefault(
            route,
            {"route": route, "live": 0, "sample": 0, "quotes": []},
        )
        route_bucket[mode] += 1

        item = {
            "id": row.id,
            "route": route,
            "origin": row.origin,
            "destination": row.destination,
            "source_id": row.source_id,
            "source_name": src.name if src else row.source_id,
            "airline": row.airline_code,
            "airline_name": airlines.get(row.airline_code, row.airline_code),
            "flight": row.flight_number,
            "lead": row.advance_purchase_days,
            "total": row.total_price,
            "site": inner.get("site"),
            "quotes_seen": inner.get("quotes_seen"),
            "can_enter_cpi": bool(row.can_enter_cpi),
            "is_live": live,
            "collection": "LIVE" if live else "SAMPLE",
            "raw_id": row.raw_id,
            "raw": inner if live else {"note": "Sample / fixture fallback for this source today."},
        }
        quotes.append(item)
        route_bucket["quotes"].append(
            {
                "source_name": item["source_name"],
                "airline_name": item["airline_name"],
                "total": item["total"],
                "is_live": live,
                "can_enter_cpi": item["can_enter_cpi"],
            }
        )

    quotes.sort(key=lambda q: (not q["is_live"], q["route"], q["source_name"], q["total"]))
    for rb in by_route.values():
        rb["quotes"].sort(key=lambda q: (not q["is_live"], q["source_name"]))

    summary = _load_day_summary()
    schedule = _schedule()
    return {
        "as_of": day.isoformat(),
        "lead": 21,
        "schedule": schedule,
        "live_count": live_n,
        "sample_count": sample_n,
        "total_count": live_n + sample_n,
        "sources": sorted(by_source.values(), key=lambda s: s["source_name"]),
        "routes": sorted(by_route.values(), key=lambda r: r["route"]),
        "quotes": quotes,
        "run_summary": (
            {
                "collected_on": summary.get("collected_on"),
                "live_ok": summary.get("live_ok"),
                "fixture_fallback": summary.get("fixture_fallback"),
                "failed": summary.get("failed"),
                "stored": summary.get("stored"),
            }
            if summary
            else None
        ),
        "note": "Daily collect for the fixed basket.",
    }
