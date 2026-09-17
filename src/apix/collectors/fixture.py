from __future__ import annotations

from datetime import date

BASE_FARE: dict[str, float] = {
    "DEL-BOM": 5450,
    "DEL-BLR": 6250,
    "BOM-BLR": 4950,
    "DEL-CCU": 6550,
    "BLR-HYD": 3350,
    "MAA-DEL": 6050,
    "BOM-HYD": 4750,
    "MAA-BLR": 4550,
    "DEL-DXB": 18400,
    "BOM-DXB": 17600,
}

AIRLINE_FACTOR = {"6E": 0.96, "AI": 1.08, "UK": 1.03, "SG": 0.94, "QP": 0.98}
LEAD_FACTOR = {
    1: 1.48,
    3: 1.34,
    7: 1.22,
    14: 1.06,
    15: 1.04,
    21: 0.93,
    30: 0.86,
    45: 0.80,
    60: 0.76,
}


def _noise(seed: str) -> float:
    h = 2166136261
    for ch in seed:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return (h / 2**32) * 0.12 + 0.94


FIXTURE_EVENTS: tuple[dict, ...] = (
    {
        "id": "east-del-ccu",
        "title": "Eastern corridor shock",
        "on": "collected_on",
        "start": "2026-09-06",
        "end": "2026-09-14",
        "factor": 1.72,
        "routes": ["DEL-CCU"],
        "note": "Deterministic fixture multiplier. Not a live disruption or weather feed.",
    },
    {
        "id": "festival-bom-blr",
        "title": "Festival travel window",
        "on": "departure",
        "start": "2026-08-27",
        "end": "2026-09-05",
        "factor": 1.48,
        "routes": ["BOM-BLR"],
        "note": "Higher fares when the travel date falls in this window.",
    },
    {
        "id": "independence-del",
        "title": "Independence-week Delhi demand",
        "on": "collected_on",
        "start": "2026-08-12",
        "end": "2026-08-16",
        "factor": 1.32,
        "hub": "DEL",
        "note": "Applies to routes that start or end in Delhi.",
    },
)


def _route_matches(route_id: str, event: dict) -> bool:
    routes = event.get("routes")
    if routes:
        return route_id in routes
    hub = event.get("hub")
    if hub:
        origin, dest = route_id.split("-", 1)
        return origin == hub or dest == hub
    return False


def _event(route_id: str, collected_on: date, departure: date) -> float:
    collected = collected_on.isoformat()
    departed = departure.isoformat()
    factor = 1.0
    for event in FIXTURE_EVENTS:
        stamp = collected if event["on"] == "collected_on" else departed
        if event["start"] <= stamp <= event["end"] and _route_matches(route_id, event):
            factor *= float(event["factor"])
    return factor


def observe_total(route_id: str, collected_on: date, lead: int, airline: str) -> tuple[float, float, float]:
    base = BASE_FARE[route_id]
    departure = date.fromordinal(collected_on.toordinal() + lead)
    lead_f = LEAD_FACTOR.get(lead, 1.0)
    weekend = 1.06 if departure.weekday() in (4, 6) else 1.0
    raw = (
        base
        * lead_f
        * AIRLINE_FACTOR.get(airline, 1.0)
        * _event(route_id, collected_on, departure)
        * weekend
        * _noise(f"{route_id}:{collected_on}:{lead}:{airline}")
    )
    total = round(raw / 10) * 10
    taxes = round(total * 0.18 / 10) * 10
    base_fare = total - taxes
    return base_fare, taxes, total


def flight_number(airline: str, origin: str, dest: str) -> str:
    n = (sum(ord(c) for c in origin + dest) % 800) + 100
    return f"{airline}{n}"


def skip_observation(source_id: str, route_id: str, collected_on: date, lead: int) -> bool:
    h = 2166136261
    seed = f"gap:{source_id}:{route_id}:{collected_on}:{lead}"
    for ch in seed:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return (h / 2**32) < 0.06
