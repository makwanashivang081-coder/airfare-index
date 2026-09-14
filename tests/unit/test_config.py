from apix.common.config import methodology, routes_config


def test_cpi_windows_locked() -> None:
    m = methodology()
    assert m["domestic"]["advance_purchase_days"] == 21
    assert m["international"]["advance_purchase_days"] == 60
    assert m["elementary_index"]["method"] == "jevons"
    assert m["missing"]["never_zero"] is True
    assert m["ota_enters_cpi"] is False


def test_basket_has_eight_domestic() -> None:
    assert len(routes_config()["members"]) == 8
