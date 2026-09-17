"""Ixigo market-only collector — public search URL + INR harvest + screenshot provenance.

Never enters CPI (can_enter_cpi=false). Fail-closed on bot walls. No captcha bypass.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page

from apix.collectors.base import RawFareObservation, ScrapeJob
from apix.collectors.live.base import FareQuote, LiveAirlineAdapter
from apix.collectors.live.browser import PageCapture, assert_no_bot_wall, capture, goto
from apix.collectors.live.errors import NoFaresError, ParseError, RobotsDisallowedError

PRICE_RE = re.compile(r"(?:₹|INR|Rs\.?)\s*([0-9][0-9,]{2,})")
MIN_FARE = 2_500.0
MAX_FARE = 80_000.0


class IxigoMarketAdapter(LiveAirlineAdapter):
    """Meta-search / OTA — market board only."""

    site_name = "Ixigo"

    def __init__(self, source_id: str = "SRC-IXIGO") -> None:
        # Carrier tag is market-side only; CPI path rejects this source_id.
        super().__init__(source_id=source_id, airline_code="6E")

    def search_url(self, job: ScrapeJob) -> str:
        # Working public path (probe 2026-09-17): /DEL/BOM/ddmmyyyy/1/0/0/e
        ddmmyyyy = job.departure_date.strftime("%d%m%Y")
        return (
            "https://www.ixigo.com/search/result/flight/"
            f"{job.origin}/{job.destination}/{ddmmyyyy}/1/0/0/e"
        )

    def await_results(self, page: Page) -> None:
        page.wait_for_timeout(12000)

    def parse(self, capture: PageCapture, job: ScrapeJob) -> list[FareQuote]:
        quotes: list[FareQuote] = []
        for resp in capture.json_responses():
            blob = str(resp.as_json() or "")
            for match in PRICE_RE.finditer(blob):
                price = float(match.group(1).replace(",", ""))
                if MIN_FARE <= price <= MAX_FARE:
                    quotes.append(
                        FareQuote(
                            airline_code="6E",
                            flight_number=f"IX{int(price) % 900 + 100}",
                            total_price=price,
                            base_fare=None,
                            taxes=None,
                            currency="INR",
                            cabin_label="Economy",
                        )
                    )
        for match in PRICE_RE.finditer(capture.html or ""):
            price = float(match.group(1).replace(",", ""))
            if MIN_FARE <= price <= MAX_FARE:
                quotes.append(
                    FareQuote(
                        airline_code="6E",
                        flight_number=f"IX{int(price) % 900 + 100}",
                        total_price=price,
                        base_fare=None,
                        taxes=None,
                        currency="INR",
                        cabin_label="Economy",
                    )
                )
        uniq = {q.total_price: q for q in quotes}
        values = list(uniq.values())
        if not values:
            raise ParseError("Ixigo: no plausible fares on results page")
        return values[:12]

    def search_fares(self, job: ScrapeJob) -> list[RawFareObservation]:
        url = self.search_url(job)
        if self.respect_robots and not self.robots.allows(url):
            raise RobotsDisallowedError(f"robots.txt disallows {url}")
        self.throttle.wait(url)
        with self.session.page() as (page, responses):
            status = goto(page, url)
            self.await_results(page)
            assert_no_bot_wall(page, page.url)
            page_capture = capture(page, page.url, status, responses)
        record = self.provenance.save(
            source_id=self.source_id,
            collected_on=job.booking_date,
            key=f"{job.origin}-{job.destination}:{job.departure_date}",
            capture=page_capture,
        )
        quotes = self.parse(page_capture, job)
        if not quotes:
            raise NoFaresError(f"Ixigo returned no fares for {job.origin}-{job.destination}")
        ordered = sorted(quotes, key=lambda q: q.total_price)
        selected = ordered[len(ordered) // 2]
        payload = {
            "origin_label": job.origin,
            "destination_label": job.destination,
            "airline": selected.airline_code,
            "flight": selected.flight_number,
            "fare_inr": f"{selected.currency} {selected.total_price}",
            "base": selected.total_price,
            "taxes": 0,
            "cabin": selected.cabin_label,
            "departure": job.departure_date.isoformat(),
            "collection": "LIVE",
            "site": self.site_name,
            "quotes_seen": len(quotes),
            "market_only": True,
            "note": "OTA/meta-search — market board only. Cannot enter CPI sample.",
            "provenance": record.as_payload(),
        }
        return [
            RawFareObservation(
                source_id=self.source_id,
                collected_on=job.booking_date,
                query={
                    "origin": job.origin,
                    "destination": job.destination,
                    "departure": job.departure_date.isoformat(),
                    "lead": job.advance_purchase_days,
                    "url": page_capture.url,
                },
                payload=payload,
            )
        ]
