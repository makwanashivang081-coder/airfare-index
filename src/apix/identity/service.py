from __future__ import annotations

import hashlib
from dataclasses import dataclass

from apix.normalization.service import CanonicalFareObservation


@dataclass(frozen=True)
class MatchedFareObservation:
    canonical: CanonicalFareObservation
    flight_id: str
    fare_product_id: str
    confidence: float


class IdentityService:
    def match(self, obs: CanonicalFareObservation) -> MatchedFareObservation:
        flight_key = "|".join(
            [
                obs.airline_code,
                obs.flight_number,
                obs.origin,
                obs.destination,
                obs.departure_date.isoformat(),
            ]
        )
        flight_id = hashlib.sha256(flight_key.encode()).hexdigest()[:24]
        fare_key = "|".join([flight_id, obs.cabin, obs.fare_family])
        fare_id = hashlib.sha256(fare_key.encode()).hexdigest()[:24]
        confidence = 1.0 if obs.flight_number and obs.airline_code else 0.4
        return MatchedFareObservation(canonical=obs, flight_id=flight_id, fare_product_id=fare_id, confidence=confidence)
