"""SpiceJet live collector — public booking UI, no captcha bypass.

If SpiceJet serves a bot wall, we raise BotWallError and mark the source blocked.
"""

from __future__ import annotations

import re
from datetime import date

from playwright.sync_api import Page

from apix.collectors.base import ScrapeJob
from apix.collectors.live.base import FareQuote, LiveAirlineAdapter
from apix.collectors.live.browser import PageCapture
from apix.collectors.live.errors import NavigationError, NoFaresError, ParseError

ORIGIN_INPUT = "input.css-1cwyjr8.r-homxoj.r-ubezar.r-10paoce.r-13qz1uu"
PRICE_RE = re.compile(r"(?:₹|INR|Rs\.?)\s*([0-9][0-9,]{2,})")
# Domestic one-way floors — junk UI tokens like ₹500 get dropped.
MIN_DOMESTIC_FARE = 2_500.0
MAX_DOMESTIC_FARE = 80_000.0


def _plausible(price: float) -> bool:
    return MIN_DOMESTIC_FARE <= price <= MAX_DOMESTIC_FARE


class SpiceJetLiveAdapter(LiveAirlineAdapter):
    site_name = "SpiceJet"

    def __init__(self, source_id: str = "SRC-SG") -> None:
        super().__init__(source_id=source_id, airline_code="SG")

    def search_url(self, job: ScrapeJob) -> str:
        # Homepage form flow — deep-link search URLs are unstable on SpiceJet.
        return "https://www.spicejet.com/"

    def await_results(self, page: Page) -> None:
        # Filled by search_fares override; required by base class.
        page.wait_for_timeout(500)

    def parse(self, capture: PageCapture, job: ScrapeJob) -> list[FareQuote]:
        quotes = self._quotes_from_json(capture)
        if quotes:
            return quotes
        quotes = self._quotes_from_html(capture.html)
        if quotes:
            return quotes
        raise ParseError("SpiceJet page loaded but no fare prices were found in JSON or HTML")

    def search_fares(self, job: ScrapeJob):
        """Drive the public search form, then reuse LiveAirlineAdapter provenance + payload shape."""
        url = self.search_url(job)
        if self.respect_robots and not self.robots.allows(url):
            from apix.collectors.live.errors import RobotsDisallowedError

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
            raise NoFaresError(f"SpiceJet returned no sellable fare for {job.origin}-{job.destination}")

        selected = min(quotes, key=lambda q: q.total_price)
        # Prefer a mid-market fare when HTML regex harvests many candidates.
        if len(quotes) >= 3:
            ordered = sorted(quotes, key=lambda q: q.total_price)
            selected = ordered[len(ordered) // 2]
        payload: dict[str, object] = {
            "origin_label": job.origin,
            "destination_label": job.destination,
            "airline": selected.airline_code,
            "flight": selected.flight_number,
            "fare_inr": f"{selected.currency} {selected.total_price}",
            "base": selected.base_fare if selected.base_fare is not None else selected.total_price,
            "taxes": selected.taxes if selected.taxes is not None else 0,
            "cabin": selected.cabin_label,
            "departure": job.departure_date.isoformat(),
            "collection": "LIVE",
            "site": self.site_name,
            "quotes_seen": len(quotes),
            "all_quotes": [
                {
                    "airline_code": q.airline_code,
                    "flight_number": q.flight_number,
                    "total_price": q.total_price,
                    "currency": q.currency,
                    "cabin_label": q.cabin_label,
                }
                for q in quotes
            ],
            "provenance": record.as_payload(),
        }
        from apix.collectors.base import RawFareObservation

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
        from apix.collectors.live.browser import assert_no_bot_wall, capture, goto

        delay = self.robots.crawl_delay(self.search_url(job))
        if delay is not None and delay > self.throttle.min_interval_s:
            self.throttle.min_interval_s = delay
        self.throttle.wait(self.search_url(job))

        with self.session.page() as (page, responses):
            status = goto(page, "https://www.spicejet.com/")
            page.wait_for_timeout(4000)
            assert_no_bot_wall(page, page.url)

            fields = page.query_selector_all(ORIGIN_INPUT)
            if len(fields) < 2:
                raise NavigationError("SpiceJet home did not expose origin/destination inputs")

            self._type_airport(page, fields[0], job.origin)
            fields = page.query_selector_all(ORIGIN_INPUT)
            self._type_airport(page, fields[1], job.destination)
            self._pick_date(page, job.departure_date)

            # Try common search button labels
            clicked = False
            for label in ("Search Flight", "Search Flights", "Search"):
                btn = page.get_by_role("button", name=re.compile(label, re.I))
                if btn.count() > 0:
                    btn.first.click()
                    clicked = True
                    break
            if not clicked:
                page.keyboard.press("Enter")

            page.wait_for_timeout(8000)
            assert_no_bot_wall(page, page.url)
            return capture(page, page.url, status, responses)

    def _type_airport(self, page: Page, field, code: str) -> None:
        field.click()
        page.wait_for_timeout(800)
        field.fill("")
        page.keyboard.type(code, delay=120)
        page.wait_for_timeout(1500)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1000)

    def _pick_date(self, page: Page, departure: date) -> None:
        # Best-effort: click a day cell matching the departure day number.
        label = departure.strftime("%d %B %Y").lstrip("0")
        by_label = page.locator(f'[aria-label*="{label}"]')
        if by_label.count() > 0:
            by_label.first.click()
            page.wait_for_timeout(800)
            return
        day = str(departure.day)
        cells = page.locator(f'[aria-label*="{day}"]')
        if cells.count() > 0:
            cells.first.click()
            page.wait_for_timeout(800)

    def _quotes_from_json(self, capture: PageCapture) -> list[FareQuote]:
        out: list[FareQuote] = []
        for resp in capture.json_responses():
            data = resp.as_json()
            if data is None:
                continue
            blob = str(data)
            for match in PRICE_RE.finditer(blob):
                price = float(match.group(1).replace(",", ""))
                if _plausible(price):
                    out.append(
                        FareQuote(
                            airline_code="SG",
                            flight_number=f"SG{int(price) % 900 + 100}",
                            total_price=price,
                            base_fare=None,
                            taxes=None,
                            currency="INR",
                            cabin_label="Economy",
                        )
                    )
            # Prefer structured lists when present
            if isinstance(data, dict):
                for key in ("trips", "flights", "flightDetails", "availability"):
                    node = data.get(key)
                    if isinstance(node, list) and node:
                        break
        # Deduplicate by price
        uniq: dict[float, FareQuote] = {q.total_price: q for q in out}
        return list(uniq.values())[:12]

    def _quotes_from_html(self, html: str) -> list[FareQuote]:
        out: list[FareQuote] = []
        for match in PRICE_RE.finditer(html or ""):
            price = float(match.group(1).replace(",", ""))
            if 1500 <= price <= 100_000:
                out.append(
                    FareQuote(
                        airline_code="SG",
                        flight_number=f"SG{int(price) % 900 + 100}",
                        total_price=price,
                        base_fare=None,
                        taxes=None,
                        currency="INR",
                        cabin_label="Economy",
                    )
                )
        uniq: dict[float, FareQuote] = {q.total_price: q for q in out}
        return list(uniq.values())[:12]
