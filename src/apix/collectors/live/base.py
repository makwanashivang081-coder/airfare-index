from __future__ import annotations

import time
from abc import abstractmethod
from dataclasses import asdict, dataclass

from playwright.sync_api import Page

from apix.collectors.base import BaseSourceAdapter, RawFareObservation, ScrapeJob
from apix.collectors.live.browser import (
    DEFAULT_USER_AGENT,
    BrowserSession,
    PageCapture,
    assert_no_bot_wall,
    capture,
    goto,
)
from apix.collectors.live.errors import (
    LiveCollectionError,
    NoFaresError,
    RobotsDisallowedError,
)
from apix.collectors.live.provenance import ProvenanceStore
from apix.collectors.live.robots import RobotsPolicy
from apix.collectors.live.throttle import HostThrottle
from apix.common.logging import get_logger

log = get_logger("apix.collectors.live")

MAX_ATTEMPTS = 3
BACKOFF_BASE_S = 4.0


@dataclass(frozen=True)
class FareQuote:
    """One sellable fare as the airline presented it, before any normalization."""

    airline_code: str
    flight_number: str
    total_price: float
    base_fare: float | None
    taxes: float | None
    currency: str
    cabin_label: str
    departure_time: str | None = None
    arrival_time: str | None = None


class LiveAirlineAdapter(BaseSourceAdapter):
    """Collects real fares from a booking site.

    Subclasses supply the URL and the parser. This class owns everything that must be true
    for every live source: robots.txt is honoured, requests are spaced out, bot walls are
    reported rather than defeated, and the page we read is kept on disk for audit.
    """

    source_id: str
    airline_code: str
    site_name: str

    def __init__(
        self,
        source_id: str,
        airline_code: str,
        *,
        session: BrowserSession | None = None,
        throttle: HostThrottle | None = None,
        robots: RobotsPolicy | None = None,
        provenance: ProvenanceStore | None = None,
        respect_robots: bool = True,
    ) -> None:
        self.source_id = source_id
        self.airline_code = airline_code
        self.session = session or BrowserSession()
        self.throttle = throttle or HostThrottle()
        self.robots = robots or RobotsPolicy(DEFAULT_USER_AGENT)
        self.provenance = provenance or ProvenanceStore()
        self.respect_robots = respect_robots

    @abstractmethod
    def search_url(self, job: ScrapeJob) -> str:
        """The booking search URL for this job."""

    @abstractmethod
    def await_results(self, page: Page) -> None:
        """Block until fares are on the page, or raise NavigationError."""

    @abstractmethod
    def parse(self, capture: PageCapture, job: ScrapeJob) -> list[FareQuote]:
        """Pull fares out of the captured page. Raise ParseError if the layout moved."""

    def search_fares(self, job: ScrapeJob) -> list[RawFareObservation]:
        url = self.search_url(job)

        if self.respect_robots and not self.robots.allows(url):
            raise RobotsDisallowedError(f"robots.txt disallows {url} for this collector")

        delay = self.robots.crawl_delay(url)
        if delay is not None and delay > self.throttle.min_interval_s:
            self.throttle.min_interval_s = delay

        page_capture = self._fetch_with_retry(url)
        record = self.provenance.save(
            source_id=self.source_id,
            collected_on=job.booking_date,
            key=f"{job.origin}-{job.destination}:{job.departure_date}",
            capture=page_capture,
        )

        quotes = self.parse(page_capture, job)
        if not quotes:
            raise NoFaresError(f"{self.site_name} returned no sellable fare for {job.origin}-{job.destination}")

        selected = min(quotes, key=lambda q: q.total_price)
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
            "all_quotes": [asdict(q) for q in quotes],
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
                    "url": url,
                },
                payload=payload,
            )
        ]

    def _fetch_with_retry(self, url: str) -> PageCapture:
        last: LiveCollectionError | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self.throttle.wait(url)
            try:
                with self.session.page() as (page, responses):
                    status = goto(page, url)
                    assert_no_bot_wall(page, url)
                    self.await_results(page)
                    assert_no_bot_wall(page, url)
                    return capture(page, url, status, responses)
            except LiveCollectionError as exc:
                last = exc
                if not exc.retryable or attempt == MAX_ATTEMPTS:
                    raise
                wait_s = BACKOFF_BASE_S * (2 ** (attempt - 1))
                log.warning("%s attempt %s/%s failed (%s), retrying in %.0fs", self.source_id, attempt, MAX_ATTEMPTS, exc, wait_s)
                time.sleep(wait_s)
        assert last is not None
        raise last

    def health_check(self) -> str:
        return "HEALTHY"
