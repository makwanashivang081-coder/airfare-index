from apix.index.jevons import jevons, price_relative


def test_price_relative_known_example() -> None:
    assert price_relative(5500, 5000) == 1.1


def test_jevons_unchained_path_100_110_121() -> None:
    r1 = price_relative(110, 100)
    r2 = price_relative(121, 110)
    i1 = 100 * jevons([r1])
    i2 = i1 * jevons([r2])
    assert round(i1, 6) == 110
    assert round(i2, 6) == 121


def test_jevons_equal_weights_geometric() -> None:
    value = jevons([1.10, 1.21], [0.5, 0.5])
    assert round(value, 6) == round((1.10 * 1.21) ** 0.5, 6)
