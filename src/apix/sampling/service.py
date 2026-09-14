from __future__ import annotations

from apix.common.config import methodology
from apix.common.enums import QualityStatus
from apix.db.models import FareObservationRow
from apix.master_data.service import Route
from apix.quality.service import ValidatedObservation
from apix.source_registry.service import Source


class SamplingService:
    def qualifies_cpi(self, validated: ValidatedObservation, route: Route, source: Source) -> bool:
        if validated.status in {QualityStatus.INVALID, QualityStatus.SCRAPE_FAILURE, QualityStatus.MISSING}:
            return False
        if not source.can_enter_cpi:
            return False
        spec = methodology()["domestic"] if route.scope == "domestic" else methodology()["international"]
        need = int(spec["advance_purchase_days"])
        obs = validated.matched.canonical
        return obs.advance_purchase_days == need and obs.cabin == "economy"

    def qualifies_realtime(self, validated: ValidatedObservation) -> bool:
        return validated.status not in {QualityStatus.INVALID, QualityStatus.SCRAPE_FAILURE}

    def to_row(self, validated: ValidatedObservation, source: Source, route: Route) -> FareObservationRow:
        obs = validated.matched.canonical
        cpi = 1 if self.qualifies_cpi(validated, route, source) else 0
        return FareObservationRow(
            id=obs.raw_id,
            raw_id=obs.raw_id,
            source_id=obs.source_id,
            origin=obs.origin,
            destination=obs.destination,
            airline_code=obs.airline_code,
            flight_number=obs.flight_number,
            departure_date=obs.departure_date,
            collected_on=obs.collected_on,
            advance_purchase_days=obs.advance_purchase_days,
            cabin=obs.cabin,
            fare_family=obs.fare_family,
            currency=obs.currency,
            base_fare=obs.base_fare,
            taxes=obs.taxes,
            total_price=obs.total_price,
            flight_id=validated.matched.flight_id,
            fare_product_id=validated.matched.fare_product_id,
            quality_status=validated.status.value,
            quality_score=validated.score,
            can_enter_cpi=cpi,
            identity_confidence=validated.matched.confidence,
        )
