from apix.common.demo import demo_lock


def test_demo_lock_shows_published_live_day() -> None:
    lock = demo_lock()
    assert lock["as_of"] == "2026-09-17"
    assert lock["collection_mode"] == "hybrid"
    assert lock["allow_live_http"] is False
    assert lock["live_data"] is True
    assert lock["story_route"] == "DEL-CCU"
    assert lock["story"]
