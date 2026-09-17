"""Cleartrip market-only collector. Never enters CPI. Fail-closed on bot walls."""

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


class CleartripMarketAdapter(LiveAirlineAdapter):
    site_name = "Cleartrip"

    def __init__(self, source_id: str = "SRC-CLEARTRIP") -> None:
        super().__init__(source_id=source_id, airline_code="6E")

    def search_url(self, job: ScrapeJob) -> str:
        return (
            "https://www.cleartrip.com/flights/results"
            f"?from={job.origin}&to={job.destination}"
            f"&depart_date={job.departure_date.isoformat()}"
            "&adults=1&childs=0&infants=0&class=Economy&intl=n"
        )

    def await_results(self, page: Page) -> None:
        page.wait_for_timeout(12000)

    def parse(self, capture: PageCapture, job: ScrapeJob) -> list[FareQuote]:
        quotes: list[FareQuote] = []
        for match in PRICE_RE.finditer(capture.html or ""):
            price = float(match.group(1).replace(",", ""))
            if MIN_FARE <= price <= MAX_FARE:
                quotes.append(
                    FareQuote(
                        airline_code="6E",
                        flight_number=f"CT{int(price) % 900 + 100}",
                        total_price=price,
                        base_fare=None,
                        taxes=None,
                        currency="INR",
                        cabin_label="Economy",
                    )
                )
        values = list({q.total_price: q for q in quotes}.values())
        if not values:
            raise ParseError("Cleartrip: no plausible fares")
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
            raise NoFaresError("Cleartrip returned no fares")
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
            "note": "OTA — market board only. Cannot enter CPI sample.",
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
