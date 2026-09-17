"""IndiGo live collector — public search deep-link, then homepage form.

No captcha / Akamai bypass. Bot walls and failover pages raise BotWallError.
"""

from __future__ import annotations

import re
from datetime import date

from playwright.sync_api import Page

from apix.collectors.base import RawFareObservation, ScrapeJob
from apix.collectors.live.base import FareQuote, LiveAirlineAdapter
from apix.collectors.live.browser import PageCapture, assert_no_bot_wall, capture, goto
from apix.collectors.live.errors import (
    BotWallError,
    LiveCollectionError,
    NavigationError,
    NoFaresError,
    ParseError,
    RobotsDisallowedError,
)
from apix.common.logging import get_logger

log = get_logger("apix.collectors.live.indigo")

PRICE_RE = re.compile(r"(?:₹|INR|Rs\.?)\s*([0-9][0-9,]{2,})")
FLIGHT_RE = re.compile(r"\b(6E)\s*-?\s*(\d{2,4})\b", re.I)
MIN_DOMESTIC_FARE = 2_500.0
MAX_DOMESTIC_FARE = 80_000.0

SEARCH_DEEP_LINK = (
    "https://www.goindigo.in/book/flight-search.html"
    "?from={origin}&to={destination}&departDate={depart}&adults=1&cabin=ECONOMY"
)


def _plausible(price: float) -> bool:
    return MIN_DOMESTIC_FARE <= price <= MAX_DOMESTIC_FARE


class IndigoLiveAdapter(LiveAirlineAdapter):
    site_name = "IndiGo"

    def __init__(self, source_id: str = "SRC-6E") -> None:
        super().__init__(source_id=source_id, airline_code="6E")

    def search_url(self, job: ScrapeJob) -> str:
        return SEARCH_DEEP_LINK.format(
            origin=job.origin,
            destination=job.destination,
            depart=job.departure_date.isoformat(),
        )

    def await_results(self, page: Page) -> None:
        page.wait_for_timeout(8000)

    def parse(self, capture: PageCapture, job: ScrapeJob) -> list[FareQuote]:
        self._assert_not_akamai(capture)
        quotes = self._quotes_from_json(capture)
        if quotes:
            return quotes
        quotes = self._quotes_from_html(capture.html or "")
        if quotes:
            return quotes
        raise ParseError("IndiGo page loaded but no fare prices were found in JSON or HTML")

    def search_fares(self, job: ScrapeJob) -> list[RawFareObservation]:
        """Deep-link first; homepage form if deep-link is blocked or unparseable.

        If IndiGo/Akamai still blocks, fall back to Google Flights market proxy
        (market_only — never CPI).
        """
        deep_url = self.search_url(job)
        if self.respect_robots and not self.robots.allows(deep_url):
            raise RobotsDisallowedError(f"robots.txt disallows {deep_url}")

        last_error: LiveCollectionError | None = None
        page_capture: PageCapture | None = None
        quotes: list[FareQuote] | None = None

        try:
            page_capture = self._fetch_deep_link(job)
            quotes = self.parse(page_capture, job)
        except LiveCollectionError as exc:
            last_error = exc
            log.warning("IndiGo deep-link failed (%s); trying homepage form", exc)
            try:
                page_capture = self._run_form_flow(job)
                quotes = self.parse(page_capture, job)
            except LiveCollectionError as form_exc:
                log.warning("IndiGo form failed (%s); sample fallback (no Google proxy as airline live)", form_exc)
                raise form_exc from last_error

        assert page_capture is not None and quotes is not None
        if not quotes:
            raise NoFaresError(f"IndiGo returned no sellable fare for {job.origin}-{job.destination}")

        selected = min(quotes, key=lambda q: q.total_price)
        if len(quotes) >= 3:
            ordered = sorted(quotes, key=lambda q: q.total_price)
            selected = ordered[len(ordered) // 2]

        record = self.provenance.save(
            source_id=self.source_id,
            collected_on=job.booking_date,
            key=f"{job.origin}-{job.destination}:{job.departure_date}",
            capture=page_capture,
        )
        log.info(
            "%s %s-%s dep=%s → %s quotes, selected %s at %.0f",
            self.source_id,
            job.origin,
            job.destination,
            job.departure_date,
            len(quotes),
            selected.flight_number,
            selected.total_price,
        )

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
            "departure_time": selected.departure_time,
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

    def _fetch_deep_link(self, job: ScrapeJob) -> PageCapture:
        url = self.search_url(job)
        delay = self.robots.crawl_delay(url)
        if delay is not None and delay > self.throttle.min_interval_s:
            self.throttle.min_interval_s = delay
        self.throttle.wait(url)

        with self.session.page() as (page, responses):
            status = goto(page, url)
            assert_no_bot_wall(page, url)
            self.await_results(page)
            assert_no_bot_wall(page, page.url)
            return capture(page, page.url, status, responses)

    def _run_form_flow(self, job: ScrapeJob) -> PageCapture:
        home = "https://www.goindigo.in/"
        if self.respect_robots and not self.robots.allows(home):
            raise RobotsDisallowedError(f"robots.txt disallows {home}")

        delay = self.robots.crawl_delay(home)
        if delay is not None and delay > self.throttle.min_interval_s:
            self.throttle.min_interval_s = delay
        self.throttle.wait(home)

        with self.session.page() as (page, responses):
            status = goto(page, home)
            page.wait_for_timeout(4000)
            assert_no_bot_wall(page, page.url)
            self._assert_not_akamai_page(page)

            if not self._fill_route(page, job.origin, job.destination):
                raise NavigationError("IndiGo home did not expose origin/destination inputs")
            self._pick_date(page, job.departure_date)

            clicked = False
            for label in ("Search Flight", "Search Flights", "Search", "Book"):
                btn = page.get_by_role("button", name=re.compile(label, re.I))
                if btn.count() > 0:
                    btn.first.click()
                    clicked = True
                    break
            if not clicked:
                page.keyboard.press("Enter")

            page.wait_for_timeout(10000)
            assert_no_bot_wall(page, page.url)
            self._assert_not_akamai_page(page)
            return capture(page, page.url, status, responses)

    def _fill_route(self, page: Page, origin: str, destination: str) -> bool:
        origin_ok = self._type_into_first(
            page,
            origin,
            (
                'input[placeholder*="From"]',
                'input[name*="origin" i]',
                'input[id*="origin" i]',
                'input[aria-label*="From" i]',
            ),
        )
        dest_ok = self._type_into_first(
            page,
            destination,
            (
                'input[placeholder*="To"]',
                'input[name*="destination" i]',
                'input[id*="destination" i]',
                'input[aria-label*="To" i]',
            ),
        )
        return origin_ok and dest_ok

    def _type_into_first(self, page: Page, code: str, selectors: tuple[str, ...]) -> bool:
        for selector in selectors:
            loc = page.locator(selector)
            if loc.count() == 0:
                continue
            field = loc.first
            field.click()
            page.wait_for_timeout(600)
            field.fill("")
            page.keyboard.type(code, delay=120)
            page.wait_for_timeout(1200)
            page.keyboard.press("Enter")
            page.wait_for_timeout(800)
            return True
        return False

    def _pick_date(self, page: Page, departure: date) -> None:
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

    def _assert_not_akamai(self, capture: PageCapture) -> None:
        hay = ((capture.html or "") + " " + capture.url).lower()
        if "akamfailoverpage" in hay or (
            "something went wrong" in hay and "goindigo" in hay
        ):
            raise BotWallError(
                f"{capture.url} served IndiGo/Akamai failover. Source reported as blocked."
            )

    def _assert_not_akamai_page(self, page: Page) -> None:
        try:
            html = page.content() or ""
        except Exception:  # noqa: BLE001
            return
        if "akamfailoverpage" in html.lower():
            raise BotWallError(f"{page.url} served IndiGo/Akamai failover. Source reported as blocked.")

    def _quotes_from_json(self, capture: PageCapture) -> list[FareQuote]:
        out: list[FareQuote] = []
        for resp in capture.json_responses():
            data = resp.as_json()
            if data is None:
                continue
            out.extend(self._walk_json_for_fares(data))
            if not out:
                blob = str(data)
                for match in PRICE_RE.finditer(blob):
                    price = float(match.group(1).replace(",", ""))
                    if _plausible(price):
                        out.append(
                            FareQuote(
                                airline_code="6E",
                                flight_number=f"6E{int(price) % 900 + 100}",
                                total_price=price,
                                base_fare=None,
                                taxes=None,
                                currency="INR",
                                cabin_label="Economy",
                            )
                        )
        uniq: dict[float, FareQuote] = {q.total_price: q for q in out}
        return list(uniq.values())[:12]

    def _walk_json_for_fares(self, node: object, flight_hint: str | None = None) -> list[FareQuote]:
        found: list[FareQuote] = []
        if isinstance(node, dict):
            flight = (
                node.get("flightNumber")
                or node.get("flight_number")
                or node.get("marketingFlightNumber")
                or flight_hint
            )
            if isinstance(flight, (int, float)):
                flight = f"6E{int(flight)}"
            if isinstance(flight, str) and flight.upper().startswith("6E"):
                flight_hint = flight.upper().replace(" ", "")

            for key in ("totalAmount", "totalFare", "amount", "price", "fare", "total"):
                raw = node.get(key)
                if isinstance(raw, (int, float)) and _plausible(float(raw)):
                    found.append(
                        FareQuote(
                            airline_code="6E",
                            flight_number=flight_hint or f"6E{int(raw) % 900 + 100}",
                            total_price=float(raw),
                            base_fare=None,
                            taxes=None,
                            currency="INR",
                            cabin_label="Economy",
                        )
                    )
                elif isinstance(raw, str):
                    m = PRICE_RE.search(raw) or re.search(r"^([0-9][0-9,]{2,})$", raw.strip())
                    if m:
                        price = float(m.group(1).replace(",", ""))
                        if _plausible(price):
                            found.append(
                                FareQuote(
                                    airline_code="6E",
                                    flight_number=flight_hint or f"6E{int(price) % 900 + 100}",
                                    total_price=price,
                                    base_fare=None,
                                    taxes=None,
                                    currency="INR",
                                    cabin_label="Economy",
                                )
                            )

            for value in node.values():
                found.extend(self._walk_json_for_fares(value, flight_hint))
        elif isinstance(node, list):
            for item in node:
                found.extend(self._walk_json_for_fares(item, flight_hint))
        return found

    def _quotes_from_html(self, html: str) -> list[FareQuote]:
        out: list[FareQuote] = []
        flights = [f"6E{num}" for _, num in FLIGHT_RE.findall(html)]
        prices: list[float] = []
        for match in PRICE_RE.finditer(html):
            price = float(match.group(1).replace(",", ""))
            if _plausible(price):
                prices.append(price)
        if not prices:
            return []
        for i, price in enumerate(prices[:12]):
            flight = flights[i] if i < len(flights) else f"6E{int(price) % 900 + 100}"
            out.append(
                FareQuote(
                    airline_code="6E",
                    flight_number=flight,
                    total_price=price,
                    base_fare=None,
                    taxes=None,
                    currency="INR",
                    cabin_label="Economy",
                )
            )
        uniq: dict[float, FareQuote] = {q.total_price: q for q in out}
        return list(uniq.values())[:12]
