from apix.common.exceptions import SampleError
from apix.index.jevons import geometric_mean, jevons, price_relative
import pytest


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


def test_missing_price_never_zero() -> None:
    with pytest.raises(SampleError):
        price_relative(0, 5000)
    with pytest.raises(SampleError):
        price_relative(5000, 0)
    with pytest.raises(SampleError):
        jevons([])
    with pytest.raises(SampleError):
        geometric_mean([100, 0, 110])


def test_weighted_jevons_matches_hand_calc() -> None:
    # two relatives, weights 0.6 / 0.4
    value = jevons([1.10, 0.95], [0.6, 0.4])
    expected = (1.10**0.6) * (0.95**0.4)
    assert round(value, 8) == round(expected, 8)
