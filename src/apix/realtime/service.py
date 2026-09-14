from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from apix.common.config import methodology
from apix.common.enums import IndexLevel, SeriesType
from apix.db.models import FareObservationRow
from apix.index.jevons import geometric_mean
from apix.index.service import IndexService


class RealtimeService:
    def publish_curves(self, session: Session, as_of: date) -> None:
        windows = [int(x) for x in methodology()["realtime_windows"]]
        rows = (
            session.query(FareObservationRow)
            .filter(FareObservationRow.collected_on == as_of)
            .all()
        )
        by_route: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
        for row in rows:
            if row.total_price <= 0:
                continue
            key = f"{row.origin}-{row.destination}"
            by_route[key][row.advance_purchase_days].append(row.total_price)
        engine = IndexService()
        for route_id, leads in by_route.items():
            for lead, prices in leads.items():
                if lead not in windows:
                    continue
                engine.publish(
                    session,
                    SeriesType.REALTIME,
                    IndexLevel.ROUTE,
                    f"{route_id}:T{lead}",
                    as_of.isoformat(),
                    geometric_mean(prices),
                    1.0,
                    len(prices),
                    [],
                )
        session.commit()

    def volatility(self, session: Session, route_id: str, as_of: date) -> str:
        origin, dest = route_id.split("-")
        rows = (
            session.query(FareObservationRow)
            .filter(
                FareObservationRow.origin == origin,
                FareObservationRow.destination == dest,
                FareObservationRow.collected_on == as_of,
                FareObservationRow.advance_purchase_days == 21,
            )
            .all()
        )
        if len(rows) < 2:
            return "LOW"
        prices = [r.total_price for r in rows]
        mean = sum(prices) / len(prices)
        var = sum((p - mean) ** 2 for p in prices) / len(prices)
        cv = (var**0.5) / mean if mean else 0
        if cv > 0.12:
            return "HIGH"
        if cv > 0.05:
            return "MEDIUM"
        return "LOW"
