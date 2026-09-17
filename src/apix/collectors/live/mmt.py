"""MakeMyTrip market-only public page collector.

Never enters CPI (can_enter_cpi=false on SRC-MMT). Fail-closed on bot walls.
"""

from __future__ import annotations

from apix.collectors.base import ScrapeJob
from apix.collectors.live.public_pages import PublicPageFareAdapter


class MakeMyTripPublicAdapter(PublicPageFareAdapter):
    site_name = "MakeMyTrip"
    homepage = "https://www.makemytrip.com/flights/"

    def __init__(self, source_id: str = "SRC-MMT") -> None:
        # Carrier tag is market-side only; identity layer still keys on source_id.
        super().__init__(source_id=source_id, airline_code="6E")

    def search_url(self, job: ScrapeJob) -> str:
        # Public flights landing — harvest INR quotes if the page exposes them.
        return (
            "https://www.makemytrip.com/flight/search"
            f"?itinerary={job.origin}-{job.destination}-{job.departure_date.strftime('%d/%m/%Y')}"
            "&tripType=O&paxType=A-1_C-0_I-0&cabinClass=E"
        )
