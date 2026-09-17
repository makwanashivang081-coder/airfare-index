"""IndiGo live adapter — parse fixtures only (no live network in CI)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from apix.collectors.base import ScrapeJob
from apix.collectors.live.browser import CapturedResponse, PageCapture
from apix.collectors.live.errors import BotWallError, ParseError
from apix.collectors.live.indigo import IndigoLiveAdapter

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "indigo"


def _job() -> ScrapeJob:
    return ScrapeJob(
        job_id="T-6E-DEL-BOM",
        source_id="SRC-6E",
        origin="DEL",
        destination="BOM",
        departure_date=date(2026, 10, 8),
        booking_date=date(2026, 9, 17),
        advance_purchase_days=21,
        priority=1,
    )


def _capture(*, html: str = "", json_body: str | None = None) -> PageCapture:
    responses: list[CapturedResponse] = []
    if json_body is not None:
        responses.append(
            CapturedResponse(
                url="https://www.goindigo.in/api/search",
                status=200,
                content_type="application/json",
                body=json_body,
            )
        )
    return PageCapture(
        url="https://www.goindigo.in/book/flight-search.html",
        status=200,
        html=html,
        screenshot_png=b"",
        responses=responses,
    )


def test_parse_structured_json_fares() -> None:
    adapter = IndigoLiveAdapter()
    body = (FIXTURES / "search_results.json").read_text(encoding="utf-8")
    quotes = adapter.parse(_capture(json_body=body), _job())
    assert len(quotes) >= 2
    assert all(q.airline_code == "6E" for q in quotes)
    assert min(q.total_price for q in quotes) == 3899.0
    assert any(q.flight_number.replace(" ", "") == "6E2341" for q in quotes)


def test_parse_html_inr_prices() -> None:
    adapter = IndigoLiveAdapter()
    html = (FIXTURES / "search_results.html").read_text(encoding="utf-8")
    quotes = adapter.parse(_capture(html=html), _job())
    assert len(quotes) == 3
    prices = sorted(q.total_price for q in quotes)
    assert prices == [3899.0, 4599.0, 5250.0]
    assert quotes[0].flight_number.startswith("6E")


def test_parse_rejects_akamai_failover() -> None:
    adapter = IndigoLiveAdapter()
    html = (FIXTURES / "akamai_failover.html").read_text(encoding="utf-8")
    with pytest.raises(BotWallError):
        adapter.parse(_capture(html=html), _job())


def test_parse_empty_page_raises() -> None:
    adapter = IndigoLiveAdapter()
    with pytest.raises(ParseError):
        adapter.parse(_capture(html="<html><body>No flights</body></html>"), _job())


def test_search_url_embeds_route_and_lead() -> None:
    adapter = IndigoLiveAdapter()
    url = adapter.search_url(_job())
    assert "from=DEL" in url
    assert "to=BOM" in url
    assert "departDate=2026-10-08" in url
    assert "cabin=ECONOMY" in url


def test_json_fixture_is_valid() -> None:
    data = json.loads((FIXTURES / "search_results.json").read_text(encoding="utf-8"))
    assert "trips" in data
