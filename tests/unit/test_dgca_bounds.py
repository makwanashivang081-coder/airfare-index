from apix.analytics.dgca_bounds import check_price, load_filed_tariffs, lookup_band


def test_tariff_sheet_loads() -> None:
    data = load_filed_tariffs()
    assert data.get("missing") is False
    assert data.get("can_enter_cpi") is False
    assert data.get("as_of") == "2026-09-01"
    assert len(data.get("routes") or []) >= 8


def test_indigo_del_bom_bidirectional() -> None:
    # Sheet lists BOM-DEL; lookup must work for DEL-BOM too.
    forward = lookup_band("6E", "DEL", "BOM")
    reverse = lookup_band("6E", "BOM", "DEL")
    assert forward is not None
    assert reverse is not None
    assert forward.filed_min_inr == reverse.filed_min_inr


def test_within_band() -> None:
    hit = check_price("6E", "DEL", "BOM", 8000)
    assert hit["status"] == "within"
    assert hit["filed_min_inr"] is not None


def test_below_band() -> None:
    hit = check_price("6E", "DEL", "BOM", 100)
    assert hit["status"] == "below_filed"


def test_no_tariff_carrier() -> None:
    hit = check_price("ZZ", "DEL", "BOM", 5000)
    assert hit["status"] == "no_tariff"
