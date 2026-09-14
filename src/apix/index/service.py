from __future__ import annotations

import json
from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from apix.common.config import methodology
from apix.common.enums import IndexLevel, SeriesType
from apix.common.time import each_date, month_key
from apix.db.models import FareObservationRow, IndexPointRow
from apix.index.jevons import geometric_mean, jevons, price_relative
from apix.master_data.service import Route


class IndexService:
    def publish(
        self,
        session: Session,
        series: SeriesType,
        level: IndexLevel,
        key: str,
        period: str,
        value: float,
        coverage: float,
        n_obs: int,
        lineage: list[str],
    ) -> None:
        method = methodology()
        pid = f"{series.value}:{level.value}:{key}:{period}"
        session.merge(
            IndexPointRow(
                id=pid,
                series=series.value,
                level=level.value,
                key=key,
                period=period,
                value=round(value, 4),
                coverage=round(coverage, 4),
                n_obs=n_obs,
                methodology_version=str(method["methodology_version"]),
                lineage_json=json.dumps(lineage[:40]),
            )
        )

    def chain_cpi(self, session: Session, routes: list[Route], start: date, end: date) -> None:
        """Daily CPI path using T+21 (or intl 60) observations only. Base first day = 100."""
        method = methodology()
        spec_dom = int(method["domestic"]["advance_purchase_days"])
        spec_int = int(method["international"]["advance_purchase_days"])
        days = each_date(start, end)
        prev_price: dict[str, float] = {}
        route_index: dict[str, float] = {r.id: 100.0 for r in routes}
        national = 100.0
        region_index = {r.region: 100.0 for r in routes}
        monthly_last: dict[str, tuple[float, float, int, list[str]]] = {}

        for day in days:
            relatives: list[float] = []
            weights: list[float] = []
            lineage: list[str] = []
            region_rels: dict[str, list[tuple[float, float]]] = defaultdict(list)
            for route in routes:
                lead = spec_int if route.scope == "international" else spec_dom
                rows = (
                    session.query(FareObservationRow)
                    .filter(
                        FareObservationRow.origin == route.origin,
                        FareObservationRow.destination == route.destination,
                        FareObservationRow.collected_on == day,
                        FareObservationRow.advance_purchase_days == lead,
                        FareObservationRow.can_enter_cpi == 1,
                    )
                    .all()
                )
                prices = [r.total_price for r in rows if r.total_price > 0]
                if not prices:
                    continue
                p_t = geometric_mean(prices)
                prev = prev_price.get(route.id)
                prev_price[route.id] = p_t
                if prev is None:
                    continue
                rel = price_relative(p_t, prev)
                route_index[route.id] *= rel
                self.publish(
                    session,
                    SeriesType.CPI,
                    IndexLevel.ROUTE,
                    route.id,
                    day.isoformat(),
                    route_index[route.id],
                    1.0,
                    len(prices),
                    [r.id for r in rows],
                )
                relatives.append(rel)
                weights.append(route.cpi_weight)
                lineage.extend(r.id for r in rows[:3])
                region_rels[route.region].append((rel, route.cpi_weight))
            if relatives:
                national *= jevons(relatives, weights)
                covered = len(relatives) / max(1, len(routes))
                self.publish(
                    session,
                    SeriesType.CPI,
                    IndexLevel.NATIONAL,
                    "INDIA",
                    day.isoformat(),
                    national,
                    covered,
                    len(relatives),
                    lineage,
                )
                self.publish(
                    session,
                    SeriesType.CPI,
                    IndexLevel.DOMESTIC,
                    "DOMESTIC",
                    day.isoformat(),
                    national,
                    covered,
                    len(relatives),
                    lineage,
                )
                monthly_last[month_key(day)] = (national, covered, len(relatives), lineage)
            for region, pairs in region_rels.items():
                rels = [p[0] for p in pairs]
                wts = [p[1] for p in pairs]
                region_index[region] *= jevons(rels, wts)
                self.publish(
                    session,
                    SeriesType.CPI,
                    IndexLevel.REGION,
                    region,
                    day.isoformat(),
                    region_index[region],
                    1.0,
                    len(pairs),
                    [],
                )
            session.flush()
        for month, (value, coverage, n_obs, lineage) in monthly_last.items():
            self.publish(
                session,
                SeriesType.CPI,
                IndexLevel.NATIONAL,
                "INDIA",
                month,
                value,
                coverage,
                n_obs,
                lineage,
            )
        session.commit()
