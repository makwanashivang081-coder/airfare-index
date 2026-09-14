from __future__ import annotations

from sqlalchemy.orm import Session

from apix.common.enums import IndexLevel, SeriesType
from apix.db.models import FareObservationRow, IndexPointRow, SourceRow


class AnalyticsService:
    def national(self, session: Session, period: str) -> IndexPointRow | None:
        return session.get(IndexPointRow, f"{SeriesType.CPI.value}:{IndexLevel.NATIONAL.value}:INDIA:{period}")

    def history(self, session: Session, level: str, key: str, series: str = "cpi") -> list[IndexPointRow]:
        return (
            session.query(IndexPointRow)
            .filter(
                IndexPointRow.series == series,
                IndexPointRow.level == level,
                IndexPointRow.key == key,
            )
            .order_by(IndexPointRow.period)
            .all()
        )

    def coverage(self, session: Session, as_of: str) -> dict:
        n_obs = session.query(FareObservationRow).filter(FareObservationRow.collected_on == as_of).count()
        n_cpi = (
            session.query(FareObservationRow)
            .filter(FareObservationRow.collected_on == as_of, FareObservationRow.can_enter_cpi == 1)
            .count()
        )
        sources = session.query(SourceRow).filter(SourceRow.enabled == 1).all()
        return {
            "observations": n_obs,
            "cpi_observations": n_cpi,
            "sources_active": len(sources),
            "source_health": {s.id: s.health for s in sources},
        }
