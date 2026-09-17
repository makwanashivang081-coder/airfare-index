from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from apix.collectors.base import RawFareObservation
from apix.common.exceptions import ContractError

AIRPORT_ALIASES = {
    "MUMBAI": "BOM",
    "BOMBAY": "BOM",
    "DELHI": "DEL",
    "BENGALURU": "BLR",
    "BANGALORE": "BLR",
    "KOLKATA": "CCU",
    "CALCUTTA": "CCU",
    "HYDERABAD": "HYD",
    "CHENNAI": "MAA",
    "MADRAS": "MAA",
    "DUBAI": "DXB",
}


@dataclass(frozen=True)
class CanonicalFareObservation:
    raw_id: str
    source_id: str
    origin: str
    destination: str
    airline_code: str
    flight_number: str
    departure_date: date
    collected_on: date
    advance_purchase_days: int
    cabin: str
    fare_family: str
    currency: str
    base_fare: float
    taxes: float
    total_price: float
    market_only: bool = False


def normalize_airport(value: str) -> str:
    v = value.strip().upper()
    if len(v) == 3 and v.isalpha():
        return v
    return AIRPORT_ALIASES.get(v, v)


def normalize_money(value: object) -> tuple[str, float]:
    if isinstance(value, (int, float)):
        return "INR", float(value)
    text = str(value).replace(",", "").replace("₹", "INR ").upper()
    match = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if not match:
        raise ContractError(f"Cannot parse money: {value}")
    currency = "INR" if "INR" in text or "RS" in text or "₹" in str(value) else "UNKNOWN"
    return currency, float(match.group(1))


class NormalizationService:
    def canonicalize(self, raw_id: str, raw: RawFareObservation) -> CanonicalFareObservation:
        payload = raw.payload
        query = raw.query
        origin = normalize_airport(str(query.get("origin") or payload.get("origin_label")))
        dest = normalize_airport(str(query.get("destination") or payload.get("destination_label")))
        currency, total = normalize_money(payload.get("fare_inr") or payload.get("total") or payload.get("base"))
        base = float(payload.get("base") or total)
        taxes = float(payload.get("taxes") or 0)
        if taxes == 0 and base == total:
            taxes = round(total * 0.18, 2)
            base = total - taxes
        departure = date.fromisoformat(str(query.get("departure") or payload.get("departure")))
        collected = raw.collected_on
        lead = int(query.get("lead") or (departure - collected).days)
        cabin_raw = str(payload.get("cabin") or "economy").lower()
        family = "saver" if "saver" in cabin_raw else "flex" if "flex" in cabin_raw else "economy"
        market_only = bool(payload.get("market_only") or payload.get("market_proxy"))
        return CanonicalFareObservation(
            raw_id=raw_id,
            source_id=raw.source_id,
            origin=origin,
            destination=dest,
            airline_code=str(payload.get("airline")),
            flight_number=str(payload.get("flight")),
            departure_date=departure,
            collected_on=collected,
            advance_purchase_days=lead,
            cabin="economy",
            fare_family=family,
            currency=currency,
            base_fare=base,
            taxes=taxes,
            total_price=total,
            market_only=market_only,
        )
