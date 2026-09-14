from __future__ import annotations

import math

from apix.common.exceptions import SampleError


def price_relative(price_t: float, price_prev: float) -> float:
    if price_t <= 0 or price_prev <= 0:
        raise SampleError("missing price is not zero; cannot form a relative")
    return price_t / price_prev


def jevons(relatives: list[float], weights: list[float] | None = None) -> float:
    if not relatives:
        raise SampleError("Jevons requires at least one relative")
    if any(r <= 0 for r in relatives):
        raise SampleError("Jevons relative must be positive")
    if weights is None:
        return math.exp(sum(math.log(r) for r in relatives) / len(relatives))
    if len(weights) != len(relatives):
        raise SampleError("weights must match relatives")
    total_w = sum(weights)
    if total_w <= 0:
        raise SampleError("weights must sum to a positive number")
    return math.exp(sum(w * math.log(r) for r, w in zip(relatives, weights, strict=True)) / total_w)


def geometric_mean(values: list[float]) -> float:
    if not values or any(v <= 0 for v in values):
        raise SampleError("geometric mean of empty or non-positive values is undefined")
    return math.exp(sum(math.log(v) for v in values) / len(values))
