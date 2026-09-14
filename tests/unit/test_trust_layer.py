from datetime import date

from apix.identity.service import IdentityService
from apix.normalization.service import CanonicalFareObservation, normalize_airport
from apix.quality.service import QualityService


def _obs(**kwargs) -> CanonicalFareObservation:
    base = dict(
        raw_id="x",
        source_id="SRC-6E",
        origin="BOM",
        destination="DEL",
        airline_code="6E",
        flight_number="6E204",
        departure_date=date(2026, 9, 21),
        collected_on=date(2026, 9, 14),
        advance_purchase_days=7,
        cabin="economy",
        fare_family="saver",
        currency="INR",
        base_fare=5000,
        taxes=900,
        total_price=5900,
    )
    base.update(kwargs)
    return CanonicalFareObservation(**base)


def test_airport_aliases() -> None:
    assert normalize_airport("Mumbai") == "BOM"
    assert normalize_airport("bom") == "BOM"


def test_same_flight_fingerprint() -> None:
    ident = IdentityService()
    a = ident.match(_obs(source_id="SRC-6E", total_price=5900))
    b = ident.match(_obs(source_id="SRC-MMT", total_price=5850))
    assert a.flight_id == b.flight_id


def test_negative_price_rejected() -> None:
    q = QualityService().evaluate(IdentityService().match(_obs(total_price=-500)))
    assert q.status.value == "INVALID"
    assert q.score == 0
