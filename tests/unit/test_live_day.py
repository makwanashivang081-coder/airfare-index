from datetime import date

from apix.analytics.live_day import live_day_payload
from apix.db.session import get_session


def test_live_day_payload_shape() -> None:
    session = get_session()
    try:
        payload = live_day_payload(session, date(2026, 9, 16))
    finally:
        session.close()
    assert payload["as_of"] == "2026-09-16"
    assert payload["lead"] == 21
    assert payload["schedule"]["local_time"] == "02:00"
    assert "live_count" in payload
    assert "sample_count" in payload
    assert payload["total_count"] == payload["live_count"] + payload["sample_count"]
    assert isinstance(payload["quotes"], list)
    assert isinstance(payload["sources"], list)
    # Board shows every airline collected that day — not live-only.
    assert payload["total_count"] >= payload["live_count"]
    if payload["quotes"]:
        q = payload["quotes"][0]
        assert q["route"]
        assert q["total"] > 0
        assert q["collection"] in {"LIVE", "SAMPLE"}
