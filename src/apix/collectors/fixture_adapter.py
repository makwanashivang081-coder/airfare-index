from __future__ import annotations

from apix.collectors.base import BaseSourceAdapter, RawFareObservation, ScrapeJob
from apix.collectors.fixture import BASE_FARE, flight_number, observe_total, skip_observation


class FixtureAdapter(BaseSourceAdapter):
    def __init__(self, source_id: str, airline_code: str) -> None:
        self.source_id = source_id
        self.airline_code = airline_code

    def search_fares(self, job: ScrapeJob) -> list[RawFareObservation]:
        route_id = f"{job.origin}-{job.destination}"
        if route_id not in BASE_FARE:
            return []
        if skip_observation(self.source_id, route_id, job.booking_date, job.advance_purchase_days):
            return []
        if self.source_id == "SRC-MMT" and skip_observation("ota", route_id, job.booking_date, job.advance_purchase_days):
            return []
        base, taxes, total = observe_total(
            route_id, job.booking_date, job.advance_purchase_days, self.airline_code
        )
        payload = {
            "origin_label": job.origin,
            "destination_label": job.destination,
            "airline": self.airline_code,
            "flight": flight_number(self.airline_code, job.origin, job.destination),
            "fare_inr": f"INR {total}",
            "base": base,
            "taxes": taxes,
            "cabin": "Economy Saver",
            "departure": job.departure_date.isoformat(),
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
                },
                payload=payload,
            )
        ]
