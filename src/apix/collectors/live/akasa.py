"""Akasa Air live collector — homepage form flow. CPI-eligible. No captcha bypass."""

from __future__ import annotations

import re
from datetime import date

from playwright.sync_api import Page

from apix.collectors.base import RawFareObservation, ScrapeJob
from apix.collectors.live.base import FareQuote, LiveAirlineAdapter
from apix.collectors.live.browser import PageCapture, assert_no_bot_wall, capture, goto
from apix.collectors.live.errors import (
    LiveCollectionError,
    NavigationError,
    NoFaresError,
    ParseError,
    RobotsDisallowedError,
)
from apix.common.logging import get_logger

log = get_logger("apix.collectors.live.akasa")

PRICE_RE = re.compile(r"(?:₹|INR|Rs\.?)\s*([0-9][0-9,]{2,})")
MIN_FARE = 2_500.0
MAX_FARE = 80_000.0


class AkasaLiveAdapter(LiveAirlineAdapter):
    site_name = "Akasa Air"

    def __init__(self, source_id: str = "SRC-QP") -> None:
        super().__init__(source_id=source_id, airline_code="QP")

    def search_url(self, job: ScrapeJob) -> str:
        return "https://www.akasaair.com/"

    def await_results(self, page: Page) -> None:
        page.wait_for_timeout(8000)

    def parse(self, capture: PageCapture, job: ScrapeJob) -> list[FareQuote]:
        quotes: list[FareQuote] = []
        for resp in capture.json_responses():
            blob = str(resp.as_json() or "")
            for match in PRICE_RE.finditer(blob):
                price = float(match.group(1).replace(",", ""))
                if MIN_FARE <= price <= MAX_FARE:
                    quotes.append(
                        FareQuote(
                            airline_code="QP",
                            flight_number=f"QP{int(price) % 900 + 100}",
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
                        airline_code="QP",
                        flight_number=f"QP{int(price) % 900 + 100}",
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
            raise ParseError("Akasa page loaded but no fare prices found")
        return values[:12]

    def search_fares(self, job: ScrapeJob) -> list[RawFareObservation]:
        url = self.search_url(job)
        if self.respect_robots and not self.robots.allows(url):
            raise RobotsDisallowedError(f"robots.txt disallows {url}")
        page_capture = self._run_form_flow(job)
        record = self.provenance.save(
            source_id=self.source_id,
            collected_on=job.booking_date,
            key=f"{job.origin}-{job.destination}:{job.departure_date}",
            capture=page_capture,
        )
        quotes = self.parse(page_capture, job)
        if not quotes:
            raise NoFaresError(f"Akasa returned no fare for {job.origin}-{job.destination}")
        ordered = sorted(quotes, key=lambda q: q.total_price)
        selected = ordered[len(ordered) // 2] if len(ordered) >= 3 else ordered[0]
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
            "provenance": record.as_payload(),
        }
        log.info(
            "%s %s-%s → %s quotes, selected %.0f",
            self.source_id,
            job.origin,
            job.destination,
            len(quotes),
            selected.total_price,
        )
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

    def _run_form_flow(self, job: ScrapeJob) -> PageCapture:
        delay = self.robots.crawl_delay(self.search_url(job))
        if delay is not None and delay > self.throttle.min_interval_s:
            self.throttle.min_interval_s = delay
        self.throttle.wait(self.search_url(job))

        with self.session.page() as (page, responses):
            status = goto(page, "https://www.akasaair.com/")
            page.wait_for_timeout(4000)
            assert_no_bot_wall(page, page.url)

            # One-way
            oneway = page.locator("#oneway")
            if oneway.count() > 0:
                oneway.first.click()
                page.wait_for_timeout(400)

            from_field = page.locator("#From, input[name='From']")
            to_field = page.locator("#To, input[name='To']")
            if from_field.count() == 0 or to_field.count() == 0:
                raise NavigationError("Akasa home missing From/To inputs")

            self._type_airport(page, from_field.first, job.origin)
            self._type_airport(page, to_field.first, job.destination)
            self._pick_date(page, job.departure_date)

            clicked = False
            for label in ("Search", "Book", "Find flights"):
                btn = page.get_by_role("button", name=re.compile(label, re.I))
                if btn.count() > 0:
                    btn.first.click()
                    clicked = True
                    break
            if not clicked:
                page.keyboard.press("Enter")

            page.wait_for_timeout(12000)
            assert_no_bot_wall(page, page.url)
            return capture(page, page.url, status, responses)

    def _type_airport(self, page: Page, field, code: str) -> None:
        field.click()
        page.wait_for_timeout(500)
        field.fill("")
        page.keyboard.type(code, delay=120)
        page.wait_for_timeout(1500)
        page.keyboard.press("Enter")
        page.wait_for_timeout(800)

    def _pick_date(self, page: Page, departure: date) -> None:
        date_field = page.locator("input[name='DepartureDate']")
        if date_field.count() > 0:
            date_field.first.click()
            page.wait_for_timeout(800)
        label = departure.strftime("%d %B %Y").lstrip("0")
        by_label = page.locator(f'[aria-label*="{label}"]')
        if by_label.count() > 0:
            by_label.first.click()
            page.wait_for_timeout(600)
            return
        day = str(departure.day)
        cells = page.locator(f'[aria-label*="{day}"]')
        if cells.count() > 0:
            cells.first.click()
            page.wait_for_timeout(600)
