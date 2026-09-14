from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class ScrapeJob:
    job_id: str
    source_id: str
    origin: str
    destination: str
    departure_date: date
    booking_date: date
    advance_purchase_days: int
    priority: int


@dataclass(frozen=True)
class RawFareObservation:
    """Layer A — what the source said. Never rewritten in place."""

    source_id: str
    collected_on: date
    query: dict[str, Any]
    payload: dict[str, Any]


class BaseSourceAdapter(ABC):
    source_id: str

    @abstractmethod
    def search_fares(self, job: ScrapeJob) -> list[RawFareObservation]:
        """Retrieve fares. Must not bypass bot walls or captcha."""

    def health_check(self) -> str:
        return "HEALTHY"
