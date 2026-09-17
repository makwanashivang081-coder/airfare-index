from __future__ import annotations

import json
from datetime import date

from sqlalchemy.orm import Session

from apix.analytics.live_day import is_live_payload
from apix.common.config import methodology
from apix.db.models import FareObservationRow, IndexPointRow, RawObservationRow, SourceRow


def _inner_from_raw(raw: RawObservationRow | None) -> dict:
    if raw is None:
        return {}
    try:
        blob = json.loads(raw.payload_json or "{}")
    except json.JSONDecodeError:
        return {}
    if isinstance(blob, dict) and isinstance(blob.get("payload"), dict):
        return blob["payload"]
    return blob if isinstance(blob, dict) else {}


def improvements_payload(session: Session, day: date) -> list[dict]:
    """Three judge-ready cards — not a wall of essays."""
    method = methodology()
    domestic_lead = int(method["domestic"]["advance_purchase_days"])
    cpi_obs = (
        session.query(FareObservationRow)
        .filter(
            FareObservationRow.collected_on == day,
            FareObservationRow.can_enter_cpi == 1,
            FareObservationRow.quality_status != "REJECT",
        )
        .count()
    )
    market_obs = (
        session.query(FareObservationRow)
        .filter(
            FareObservationRow.collected_on == day,
            FareObservationRow.can_enter_cpi == 0,
        )
        .count()
    )
    with_raw = (
        session.query(FareObservationRow)
        .filter(FareObservationRow.collected_on == day, FareObservationRow.raw_id.isnot(None))
        .count()
    )
    total = session.query(FareObservationRow).filter(FareObservationRow.collected_on == day).count()

    return [
        {
            "id": "daily",
            "title": "Daily signal",
            "official_pain": "Official airfare in CPI is slow",
            "we_add": "Same basket every day",
            "why_government_cares": "See airfares move between monthly CPI prints",
            "prototype_shows": f"{cpi_obs} index quotes today",
        },
        {
            "id": "audit",
            "title": "Audit trail",
            "official_pain": "Hard to defend a number",
            "we_add": "Click down to a receipt",
            "why_government_cares": "Every index quote has a saved receipt",
            "prototype_shows": f"{with_raw}/{total} linked to raw data",
        },
        {
            "id": "clean",
            "title": "Clean sample",
            "official_pain": "Shopping sites muddy official series",
            "we_add": "Airlines in CPI · market kept separate",
            "why_government_cares": "The inflation path stays clean",
            "prototype_shows": f"{cpi_obs} CPI · {market_obs} market",
        },
    ]


def proof_for_route(session: Session, route_id: str, day: date) -> dict:
    origin, dest = route_id.upper().split("-")
    method = methodology()
    domestic_lead = int(method["domestic"]["advance_purchase_days"])

    national = session.get(IndexPointRow, f"cpi:national:INDIA:{day.isoformat()}")
    route_point = session.get(IndexPointRow, f"cpi:route:{origin}-{dest}:{day.isoformat()}")

    sources = {s.id: s for s in session.query(SourceRow).all()}
    obs = (
        session.query(FareObservationRow)
        .filter(
            FareObservationRow.origin == origin,
            FareObservationRow.destination == dest,
            FareObservationRow.collected_on == day,
            FareObservationRow.can_enter_cpi == 1,
            FareObservationRow.advance_purchase_days == domestic_lead,
            FareObservationRow.quality_status != "REJECT",
        )
        .order_by(FareObservationRow.total_price.asc())
        .all()
    )

    chain = []
    live_n = 0
    for row in obs[:8]:
        raw = session.get(RawObservationRow, row.raw_id)
        src = sources.get(row.source_id)
        inner = _inner_from_raw(raw)
        live = is_live_payload(inner)
        if live:
            live_n += 1
        payload = None
        if raw is not None:
            try:
                payload = json.loads(raw.payload_json)
            except json.JSONDecodeError:
                payload = {"error": "unreadable raw payload"}
        chain.append(
            {
                "observation_id": row.id,
                "source_id": row.source_id,
                "source_name": src.name if src else row.source_id,
                "source_type": src.type if src else None,
                "allow_http": bool(src.allow_http) if src else False,
                "collection_method": src.collection_method if src else None,
                "airline": row.airline_code,
                "flight": row.flight_number,
                "lead": row.advance_purchase_days,
                "total": row.total_price,
                "quality": row.quality_status,
                "quality_score": row.quality_score,
                "flight_id": row.flight_id,
                "raw_id": row.raw_id,
                "is_live": live,
                "site": inner.get("site"),
                "collection": "LIVE" if live else "SAMPLE",
                "cabin": inner.get("cabin") or row.cabin,
                "raw": {
                    "storage_path": raw.storage_path if raw else None,
                    "parser_version": raw.parser_version if raw else None,
                    "collected_at": raw.collected_at.isoformat() if raw else None,
                    "payload": payload,
                    "inner": inner,
                },
            }
        )

    story = None
    if route_id.upper() == "DEL-CCU":
        story = {
            "headline": "Eastern corridor example (DEL→CCU)",
            "body": "",
        }

    return {
        "as_of": day.isoformat(),
        "route_id": f"{origin}-{dest}",
        "story": story,
        "spec": {
            "cabin": "economy",
            "advance_purchase_days": domestic_lead,
            "ota_enters_cpi": False,
            "missing_never_zero": True,
            "one_liner": "We augment MoSPI CPI — we do not replace it.",
        },
        "national": (
            {
                "value": round(national.value, 2),
                "coverage": national.coverage,
                "n_obs": national.n_obs,
                "methodology_version": national.methodology_version,
            }
            if national
            else None
        ),
        "route_index": (
            {
                "value": round(route_point.value, 2),
                "coverage": route_point.coverage,
                "n_obs": route_point.n_obs,
                "methodology_version": route_point.methodology_version,
            }
            if route_point
            else None
        ),
        "cpi_observations": chain,
        "receipt": {
            "live_quotes_in_chain": live_n,
            "sample_quotes_in_chain": max(0, len(chain) - live_n),
            "message": "",
        },
    }
