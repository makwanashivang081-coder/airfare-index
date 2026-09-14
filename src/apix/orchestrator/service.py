from __future__ import annotations

from datetime import date

from apix.collectors.base import ScrapeJob
from apix.common.config import methodology
from apix.common.time import add_days
from apix.master_data.service import Route


class Orchestrator:
    def plan_day(self, collected_on: date, routes: list[Route], windows: list[int] | None = None) -> list[ScrapeJob]:
        method = methodology()
        wins = windows or list(method["realtime_windows"])
        jobs: list[ScrapeJob] = []
        n = 0
        for route in routes:
            if route.scope == "international":
                leads = [int(method["international"]["advance_purchase_days"])]
            else:
                leads = wins
            for lead in leads:
                n += 1
                jobs.append(
                    ScrapeJob(
                        job_id=f"JOB-{collected_on.isoformat()}-{route.id}-T{lead}-{n}",
                        source_id="*",
                        origin=route.origin,
                        destination=route.destination,
                        departure_date=add_days(collected_on, lead),
                        booking_date=collected_on,
                        advance_purchase_days=lead,
                        priority=self._priority(route, lead),
                    )
                )
        return jobs

    def _priority(self, route: Route, lead: int) -> int:
        # High traffic + CPI window get collected first. Feedback loop uses volatility later.
        score = int(route.market_weight * 100)
        if lead in (1, 7, 21):
            score += 20
        return score
