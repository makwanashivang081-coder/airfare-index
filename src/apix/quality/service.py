from __future__ import annotations

from dataclasses import dataclass

from apix.common.config import methodology
from apix.common.enums import QualityStatus
from apix.identity.service import MatchedFareObservation


@dataclass(frozen=True)
class ValidatedObservation:
    matched: MatchedFareObservation
    status: QualityStatus
    score: float
    reasons: tuple[str, ...]


class QualityService:
    def evaluate(self, matched: MatchedFareObservation) -> ValidatedObservation:
        obs = matched.canonical
        reasons: list[str] = []
        score = 1.0
        status = QualityStatus.OBSERVED
        if obs.total_price <= 0:
            return ValidatedObservation(matched, QualityStatus.INVALID, 0.0, ("non_positive_price",))
        if obs.currency != "INR":
            reasons.append("currency")
            score -= 0.4
        if obs.advance_purchase_days < 0:
            return ValidatedObservation(matched, QualityStatus.INVALID, 0.0, ("departure_before_collection",))
        if not obs.flight_number:
            reasons.append("flight")
            score -= 0.2
        if matched.confidence < 0.5:
            reasons.append("identity")
            score -= 0.2
        score = max(0.0, min(1.0, score))
        reject = float(methodology()["quality"]["reject_below"])
        warn = float(methodology()["quality"]["warning_below"])
        if score < reject:
            status = QualityStatus.INVALID
        elif score < warn:
            status = QualityStatus.WARNING
        return ValidatedObservation(matched, status, score, tuple(reasons))
