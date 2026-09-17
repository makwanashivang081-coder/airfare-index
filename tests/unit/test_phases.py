from apix.analytics.phases import phases_status
from apix.collectors.hub import AdapterHub
from apix.source_registry.service import Source
from apix.common.enums import CollectionMethod, SourceStatus, SourceType


def test_simple_v2_phases_honest_progress() -> None:
    payload = phases_status()
    assert payload["plan"] == "simple-v2"
    assert len(payload["phases"]) == 6
    by_id = {p["id"]: p for p in payload["phases"]}
    assert by_id["0"]["status"] == "completed"
    assert by_id["1"]["status"] == "completed"
    assert by_id["2"]["status"] == "completed"
    assert by_id["3"]["status"] == "completed"
    assert by_id["4"]["status"] == "completed"
    assert by_id["5"]["status"] == "completed"
    assert payload["live_data"] is True


def test_hub_serves_spicejet_and_akasa_fixtures() -> None:
    hub = AdapterHub()
    for code, adapter in (("SG", "spicejet_live"), ("QP", "akasa_fixture")):
        source = Source(
            id=f"SRC-{code}",
            name=code,
            type=SourceType.AIRLINE,
            airline_code=code,
            collection_method=CollectionMethod.FIXTURE,
            adapter=adapter,
            enabled=True,
            priority=1,
            can_enter_cpi=True,
            allow_http=False,
            health=SourceStatus.HEALTHY,
            note=None,
        )
        assert hub.adapter_for(source).airline_code == code


def test_hub_live_routes_indigo_and_mmt() -> None:
    hub = AdapterHub()
    indigo = Source(
        id="SRC-6E",
        name="IndiGo",
        type=SourceType.AIRLINE,
        airline_code="6E",
        collection_method=CollectionMethod.HTTP,
        adapter="indigo_live",
        enabled=True,
        priority=1,
        can_enter_cpi=True,
        allow_http=True,
        health=SourceStatus.HEALTHY,
        note=None,
    )
    assert hub.adapter_for(indigo).airline_code == "6E"
    mmt = Source(
        id="SRC-MMT",
        name="MakeMyTrip",
        type=SourceType.OTA,
        airline_code=None,
        collection_method=CollectionMethod.HTTP,
        adapter="mmt_live",
        enabled=True,
        priority=6,
        can_enter_cpi=False,
        allow_http=True,
        health=SourceStatus.HEALTHY,
        note=None,
    )
    assert hub.adapter_for(mmt).source_id == "SRC-MMT"
