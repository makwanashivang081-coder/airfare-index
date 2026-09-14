from datetime import date

from apix.collectors.base import ScrapeJob
from apix.collectors.hub import AdapterHub
from apix.common.enums import CollectionMethod, SourceStatus, SourceType
from apix.common.exceptions import ContractError
from apix.source_registry.service import Source


def test_http_adapter_forbidden() -> None:
    source = Source(
        id="SRC-BAD",
        name="Bad",
        type=SourceType.OTA,
        airline_code=None,
        collection_method=CollectionMethod.HTTP,
        adapter="x",
        enabled=True,
        priority=1,
        can_enter_cpi=False,
        allow_http=True,
        health=SourceStatus.HEALTHY,
        note=None,
    )
    try:
        AdapterHub().adapter_for(source)
        raise AssertionError("expected ContractError")
    except ContractError:
        pass


def test_fixture_adapter_contract() -> None:
    source = Source(
        id="SRC-6E",
        name="IndiGo",
        type=SourceType.AIRLINE,
        airline_code="6E",
        collection_method=CollectionMethod.FIXTURE,
        adapter="indigo_fixture",
        enabled=True,
        priority=1,
        can_enter_cpi=True,
        allow_http=False,
        health=SourceStatus.HEALTHY,
        note=None,
    )
    job = ScrapeJob(
        job_id="j1",
        source_id="SRC-6E",
        origin="DEL",
        destination="BOM",
        departure_date=date(2026, 9, 21),
        booking_date=date(2026, 9, 14),
        advance_purchase_days=7,
        priority=1,
    )
    rows = AdapterHub().execute(source, job)
    assert rows
    assert "origin" in rows[0].query
    assert rows[0].payload["airline"] == "6E"
