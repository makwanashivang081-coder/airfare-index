"""Vistara (UK) — no dedicated live booking UI (brand folded into Air India).

Do not invent Google proxy rows under SRC-UK. Day job uses sample; market live is SRC-GFL.
"""

from __future__ import annotations

from apix.collectors.base import RawFareObservation, ScrapeJob
from apix.collectors.live.base import LiveAirlineAdapter
from apix.collectors.live.browser import PageCapture
from apix.collectors.live.errors import NavigationError
from playwright.sync_api import Page


class VistaraLiveAdapter(LiveAirlineAdapter):
    site_name = "Vistara"

    def __init__(self, source_id: str = "SRC-UK") -> None:
        super().__init__(source_id=source_id, airline_code="UK")

    def search_url(self, job: ScrapeJob) -> str:
        return "https://www.airvistara.com/"

    def await_results(self, page: Page) -> None:
        page.wait_for_timeout(500)

    def parse(self, capture: PageCapture, job: ScrapeJob) -> list:
        raise NavigationError(
            "Vistara brand has no dedicated live booking UI; use sample for SRC-UK. "
            "Market live is under Google Flights (SRC-GFL)."
        )

    def search_fares(self, job: ScrapeJob) -> list[RawFareObservation]:
        raise NavigationError(
            "Vistara brand has no dedicated live booking UI; use sample for SRC-UK. "
            "Market live is under Google Flights (SRC-GFL)."
        )
