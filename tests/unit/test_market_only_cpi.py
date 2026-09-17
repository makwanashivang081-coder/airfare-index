"""market_only / market_proxy must never qualify for CPI."""

from datetime import date

from apix.identity.service import MatchedFareObservation
from apix.master_data.service import Route
from apix.normalization.service import CanonicalFareObservation
from apix.quality.service import QualityService, ValidatedObservation
from apix.common.enums import QualityStatus, CollectionMethod, SourceStatus, SourceType
from apix.sampling.service import SamplingService
from apix.source_registry.service import Source


def _obs(*, market_only: bool) -> CanonicalFareObservation:
    return CanonicalFareObservation(
        raw_id="r1",
        source_id="SRC-AI",
        origin="DEL",
        destination="BOM",
        airline_code="AI",
        flight_number="AI101",
        departure_date=date(2026, 10, 8),
        collected_on=date(2026, 9, 17),
        advance_purchase_days=21,
        cabin="economy",
        fare_family="economy",
        currency="INR",
        base_fare=7000,
        taxes=1000,
        total_price=8000,
        market_only=market_only,
    )


def test_market_proxy_never_enters_cpi() -> None:
    source = Source(
        id="SRC-AI",
        name="Air India",
        type=SourceType.AIRLINE,
        airline_code="AI",
        collection_method=CollectionMethod.HTTP,
        adapter="air_india_live",
        enabled=True,
        priority=1,
        can_enter_cpi=True,
        allow_http=True,
        health=SourceStatus.HEALTHY,
        note=None,
    )
    route = Route(
        id="DEL-BOM",
        origin="DEL",
        destination="BOM",
        scope="domestic",
        region="west",
        cpi_weight=0.22,
        market_weight=0.24,
    )
    sampling = SamplingService()
    matched = MatchedFareObservation(
        canonical=_obs(market_only=True),
        flight_id="f1",
        fare_product_id="p1",
        confidence=1.0,
    )
    validated = ValidatedObservation(matched, QualityStatus.OBSERVED, 1.0, ())
    assert sampling.qualifies_cpi(validated, route, source) is False

    matched2 = MatchedFareObservation(
        canonical=_obs(market_only=False),
        flight_id="f1",
        fare_product_id="p1",
        confidence=1.0,
    )
    validated2 = ValidatedObservation(matched2, QualityStatus.OBSERVED, 1.0, ())
    assert sampling.qualifies_cpi(validated2, route, source) is True
