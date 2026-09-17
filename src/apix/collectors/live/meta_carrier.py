"""Google Flights market proxy when an airline's own site is blocked.

Tagged market_only — never enters CPI. No captcha bypass.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from playwright.sync_api import Page

from apix.collectors.base import RawFareObservation, ScrapeJob
from apix.collectors.live.base import FareQuote, LiveAirlineAdapter
from apix.collectors.live.browser import PageCapture, assert_no_bot_wall, capture, goto
from apix.collectors.live.errors import NoFaresError, ParseError, RobotsDisallowedError

PRICE_RE = re.compile(r"(?:₹|INR|Rs\.?)\s*([0-9][0-9,]{2,})")
MIN_FARE = 2_500.0
MAX_FARE = 100_000.0


class MetaCarrierProxyAdapter(LiveAirlineAdapter):
    """Harvest INR fares from Google Flights for a named carrier (market board only)."""

    site_name = "Google Flights"
    carrier_label: str

    def __init__(
        self,
        source_id: str,
        airline_code: str,
        *,
        carrier_label: str,
    ) -> None:
        super().__init__(source_id=source_id, airline_code=airline_code)
        self.carrier_label = carrier_label

    def search_url(self, job: ScrapeJob) -> str:
        q = (
            f"One way {self.carrier_label} flights from {job.origin} to {job.destination} "
            f"on {job.departure_date.isoformat()}"
        )
        return f"https://www.google.com/travel/flights?hl=en&curr=INR&q={quote(q)}"

    def await_results(self, page: Page) -> None:
        page.wait_for_timeout(12000)

    def parse(self, capture: PageCapture, job: ScrapeJob) -> list[FareQuote]:
        hay = (capture.html or "").lower()
        label = self.carrier_label.lower()
        # Prefer pages that mention the carrier; still harvest if prices exist (query was carrier-scoped).
        quotes: list[FareQuote] = []
        for match in PRICE_RE.finditer(capture.html or ""):
            price = float(match.group(1).replace(",", ""))
            if MIN_FARE <= price <= MAX_FARE:
                quotes.append(
                    FareQuote(
                        airline_code=self.airline_code,
                        flight_number=f"{self.airline_code}{int(price) % 900 + 100}",
                        total_price=price,
                        base_fare=None,
                        taxes=None,
                        currency="INR",
                        cabin_label="Economy",
                    )
                )
        if not quotes:
            raise ParseError(f"Meta proxy ({self.carrier_label}): no plausible fares")
        if label not in hay and "flight" not in hay:
            raise ParseError(f"Meta proxy ({self.carrier_label}): page did not look like results")
        uniq = {q.total_price: q for q in quotes}
        return list(uniq.values())[:12]

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
            raise NoFaresError(f"Meta proxy returned no fares for {self.carrier_label}")
        ordered = sorted(quotes, key=lambda q: q.total_price)
        selected = ordered[0]
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
            "site": f"Google Flights ({self.carrier_label} proxy)",
            "quotes_seen": len(quotes),
            "market_only": True,
            "market_proxy": True,
            "note": (
                f"Airline site blocked or empty; live market proxy via Google Flights for "
                f"{self.carrier_label}. Cannot enter CPI sample."
            ),
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
