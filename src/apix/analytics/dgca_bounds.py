"""DGCA / airline filed-tariff bounds — validation check only.

Never enters the CPI sample. Compares observed basket fares to filed
min/max bands from airline tariff sheets (Sep 2026 extract).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from apix.common.config import methodology
from apix.common.logging import backend_root
from apix.db.models import FareObservationRow

# Tax / fee buffer: some sheets lean base-fare; our quotes are usually totals.
_LOW_FACTOR = 0.85
_HIGH_FACTOR = 1.25

_REF = backend_root() / "data" / "dgca" / "filed_tariffs_2026-09.json"


@dataclass(frozen=True)
class FiledBand:
    airline: str
    origin: str
    destination: str
    filed_min_inr: float
    filed_max_inr: float


@lru_cache(maxsize=1)
def load_filed_tariffs() -> dict:
    if not _REF.is_file():
        return {
            "as_of": None,
            "source": None,
            "role": "validation_check_only",
            "can_enter_cpi": False,
            "routes": [],
            "missing": True,
        }
    data = json.loads(_REF.read_text(encoding="utf-8"))
    data["missing"] = False
    return data


def _index_bands(data: dict) -> dict[tuple[str, str, str], FiledBand]:
    out: dict[tuple[str, str, str], FiledBand] = {}
    for row in data.get("routes") or []:
        airline = str(row["airline"]).upper()
        origin = str(row["origin"]).upper()
        dest = str(row["destination"]).upper()
        band = FiledBand(
            airline=airline,
            origin=origin,
            destination=dest,
            filed_min_inr=float(row["filed_min_inr"]),
            filed_max_inr=float(row["filed_max_inr"]),
        )
        out[(airline, origin, dest)] = band
        # Tariff sheets often list one direction only — allow reverse lookup.
        out.setdefault((airline, dest, origin), band)
    return out


def lookup_band(airline: str, origin: str, destination: str) -> FiledBand | None:
    bands = _index_bands(load_filed_tariffs())
    return bands.get((airline.upper(), origin.upper(), destination.upper()))


def check_price(airline: str, origin: str, destination: str, price_inr: float) -> dict:
    """Soft check. Never rejects CPI membership by itself."""
    band = lookup_band(airline, origin, destination)
    if band is None:
        return {
            "status": "no_tariff",
            "airline": airline,
            "origin": origin,
            "destination": destination,
            "price_inr": price_inr,
            "filed_min_inr": None,
            "filed_max_inr": None,
            "message": "No filed tariff band for this airline/route in the Sep-2026 sheet.",
        }
    low = band.filed_min_inr * _LOW_FACTOR
    high = band.filed_max_inr * _HIGH_FACTOR
    if price_inr < low:
        status = "below_filed"
        message = "Observed fare is below the filed minimum band (after tax buffer)."
    elif price_inr > high:
        status = "above_filed"
        message = "Observed fare is above the filed maximum band (after tax buffer)."
    else:
        status = "within"
        message = "Observed fare sits inside the filed airline band."
    return {
        "status": status,
        "airline": airline,
        "origin": origin,
        "destination": destination,
        "price_inr": round(price_inr, 0),
        "filed_min_inr": band.filed_min_inr,
        "filed_max_inr": band.filed_max_inr,
        "band_low_inr": round(low, 0),
        "band_high_inr": round(high, 0),
        "message": message,
    }


def dgca_check_for_day(session: Session, day, route_id: str | None = None) -> dict:
    """Summarise CPI-sample quotes vs filed bands for a day (optional route)."""
    meta = load_filed_tariffs()
    method = methodology()
    domestic_lead = int(method["domestic"]["advance_purchase_days"])
    q = session.query(FareObservationRow).filter(
        FareObservationRow.collected_on == day,
        FareObservationRow.can_enter_cpi == 1,
        FareObservationRow.advance_purchase_days == domestic_lead,
        FareObservationRow.quality_status != "REJECT",
    )
    if route_id:
        origin, dest = route_id.upper().split("-")
        q = q.filter(
            FareObservationRow.origin == origin,
            FareObservationRow.destination == dest,
        )
    rows = q.all()
    checks = [
        check_price(row.airline_code, row.origin, row.destination, float(row.total_price))
        for row in rows
    ]
    counts = {"within": 0, "below_filed": 0, "above_filed": 0, "no_tariff": 0}
    for c in checks:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    checked = counts["within"] + counts["below_filed"] + counts["above_filed"]
    within_pct = round(100.0 * counts["within"] / checked, 1) if checked else None
    return {
        "as_of": day.isoformat() if hasattr(day, "isoformat") else str(day),
        "route_id": route_id,
        "tariff_sheet_as_of": meta.get("as_of"),
        "role": "validation_check_only",
        "can_enter_cpi": False,
        "source_note": meta.get("source"),
        "quotes_checked": len(checks),
        "counts": counts,
        "within_pct": within_pct,
        "headline": (
            f"{counts['within']}/{checked} CPI quotes inside filed bands"
            if checked
            else "No CPI quotes to check against filed tariffs"
        ),
        "one_liner": "DGCA/airline tariff sheets check our quotes — they do not enter the inflation sample.",
        "samples": checks[:12],
    }
