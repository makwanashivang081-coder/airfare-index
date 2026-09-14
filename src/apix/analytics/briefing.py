from __future__ import annotations

from apix.collectors.fixture import FIXTURE_EVENTS
from apix.common.config import methodology, routes_config, settings


def public_methodology() -> dict:
    method = methodology()
    cfg = settings()
    routes = routes_config()
    international = routes.get("international") or {}
    return {
        "version": method["methodology_version"],
        "base_year": method["base_year"],
        "prototype_link": method["prototype_link"],
        "elementary": method["elementary_index"]["method"],
        "aggregation": method["aggregation"]["method"],
        "domestic_lead": method["domestic"]["advance_purchase_days"],
        "international_lead": method["international"]["advance_purchase_days"],
        "cabin": method["domestic"]["cabin"],
        "trip": method["domestic"]["trip"],
        "realtime_windows": method["realtime_windows"],
        "ota_enters_cpi": bool(method["ota_enters_cpi"]),
        "allow_live_http": bool(cfg.get("allow_live_http", False)),
        "missing_policy": method["missing"]["policy"],
        "never_zero": bool(method["missing"]["never_zero"]),
        "basket_id": routes["basket_id"],
        "international_basket": international.get("basket_id"),
        "international_members": [
            f"{row['origin']}-{row['destination']}" for row in international.get("members", [])
        ],
        "quality": method["quality"],
    }


def events_payload(as_of: str) -> list[dict]:
    payload: list[dict] = []
    for event in FIXTURE_EVENTS:
        item = dict(event)
        item["active"] = bool(event["on"] == "collected_on" and event["start"] <= as_of <= event["end"])
        payload.append(item)
    return payload


def build_callouts(*, index: dict, regions: list[dict], events: list[dict]) -> list[dict]:
    items = [
        {
            "tone": "info",
            "title": "Prototype series — not official CPI",
            "body": "Chained from the first complete sample month = 100 using CPI 2024 methods (Jevons elementary, T+21 domestic). It augments MoSPI/NSO CPI. It does not replace it.",
        },
        {
            "tone": "info",
            "title": "Collection is fixture, not a live scrape",
            "body": "Airline and OTA adapters share the live collection contract. HTTP booking-page collection is off. Missing prices are skipped, never written as zero.",
        },
    ]
    east = next((row for row in regions if row.get("key") == "east"), None)
    if east is not None and float(east["value"]) >= 130:
        items.append(
            {
                "tone": "alert",
                "title": f"East region index is {float(east['value']):.1f}",
                "body": "DEL–CCU is in the CPI basket at 10% weight. A fixture shock of ×1.72 sits on that corridor from 6–14 Sep 2026. Outliers are not silently dropped.",
            }
        )
    if index.get("change_yoy") is None:
        items.append(
            {
                "tone": "muted",
                "title": "Year-on-year is not published yet",
                "body": "The prototype sample starts in 2026. Month-on-month is available. YoY needs the same month in the prior year.",
            }
        )
    items.append(
        {
            "tone": "muted",
            "title": "International basket is configured, not collected",
            "body": "DEL–DXB and BOM–DXB are in config for a T+60 CPI spec. This pipeline currently publishes domestic routes only.",
        }
    )
    return items
