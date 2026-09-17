"""Merge live airline collects into today's observations, then refresh index.

Falls back to fixture adapter per source/route if live fails (bot wall, parse error).
"""

from __future__ import annotations

import os
from datetime import date

from sqlalchemy.orm import Session

from apix.collectors.base import ScrapeJob
from apix.collectors.fixture_adapter import FixtureAdapter
from apix.collectors.hub import AdapterHub
from apix.collectors.live.browser import BrowserSession
from apix.collectors.live.errors import LiveCollectionError
from apix.common.config import methodology
from apix.common.demo import as_of_date
from apix.common.logging import get_logger
from apix.common.time import add_days
from apix.db.models import IndexPointRow, SourceRow
from apix.identity.service import IdentityService
from apix.index.service import IndexService
from apix.master_data.service import MasterDataService
from apix.normalization.service import NormalizationService
from apix.pipeline import Pipeline
from apix.quality.service import QualityService
from apix.raw_data.service import RawDataService
from apix.realtime.service import RealtimeService
from apix.sampling.service import SamplingService
from apix.source_registry.service import Source, SourceRegistryService

log = get_logger("apix.live.day")

# Airlines we attempt live for when ALLOW_LIVE_HTTP=true
# 6E/AI/UK sites block or have no UI — sample only; market live is SRC-GFL / Ixigo / Cleartrip
# Override with LIVE_AIRLINES=SG,QP,6E,AI,UK  and LIVE_MARKET=1
def _live_codes() -> set[str]:
    raw = os.environ.get("LIVE_AIRLINES", "SG,QP")
    return {part.strip().upper() for part in raw.split(",") if part.strip()}


def _live_market() -> bool:
    return os.environ.get("LIVE_MARKET", "true").lower() in {"1", "true", "yes"}


_MARKET_SOURCE_IDS = frozenset({"SRC-IXIGO", "SRC-GFL", "SRC-CLEARTRIP"})
# MMT left out of live market attempts — consistent HTTP/2/timeout failures; fixture only.


class LiveDayService:
    def __init__(self) -> None:
        self.pipeline = Pipeline()
        self.hub = AdapterHub()
        self.raw = RawDataService()
        self.normalizer = NormalizationService()
        self.identity = IdentityService()
        self.quality = QualityService()
        self.sampling = SamplingService()
        self.master = MasterDataService()
        self.registry = SourceRegistryService()
        self.index = IndexService()
        self.realtime = RealtimeService()
        self.parser_version = str(methodology()["versions"]["parser"]) + "+live"

    def run(self, collected_on: date | None = None, leads: list[int] | None = None) -> dict:
        allow = os.environ.get("ALLOW_LIVE_HTTP", "false").lower() in {"1", "true", "yes"}
        day = collected_on or date.today()
        windows = leads or [21]
        session = self.pipeline.init_db()
        routes = [r for r in self.master.routes(session) if r.scope == "domestic"]
        market_ids = _MARKET_SOURCE_IDS | {"SRC-MMT"}  # MMT fixture-only (live attempts skipped)
        sources = [
            s
            for s in self.registry.list_enabled(session)
            if s.airline_code or s.id in market_ids
        ]

        summary = {
            "collected_on": day.isoformat(),
            "allow_live_http": allow,
            "live_ok": 0,
            "fixture_fallback": 0,
            "failed": 0,
            "stored": 0,
            "details": [],
        }

        # Share one browser for the whole day when live is on.
        session_browser: BrowserSession | None = None
        if allow:
            session_browser = BrowserSession(headless=True)
            session_browser.start()

        try:
            for route in routes:
                for lead in windows:
                    job = ScrapeJob(
                        job_id=f"DAY-{day.isoformat()}-{route.id}-T{lead}",
                        source_id="*",
                        origin=route.origin,
                        destination=route.destination,
                        departure_date=add_days(day, lead),
                        booking_date=day,
                        advance_purchase_days=lead,
                        priority=1,
                    )
                    for source in sources:
                        stored, mode, err = self._collect_one(
                            session, route, source, job, allow, session_browser
                        )
                        summary["stored"] += stored
                        if mode == "live":
                            summary["live_ok"] += 1
                        elif mode == "fixture":
                            summary["fixture_fallback"] += 1
                        else:
                            summary["failed"] += 1
                        summary["details"].append(
                            {
                                "route": route.id,
                                "lead": lead,
                                "source": source.id,
                                "mode": mode,
                                "stored": stored,
                                "error": err,
                            }
                        )
            session.commit()

            # Rebuild published series. Keep fare observations; only refresh index points.
            chain_end = max(day, as_of_date())
            chain_start = date(2026, 6, 1)
            session.query(IndexPointRow).delete()
            session.commit()
            domestic = [r for r in self.master.routes(session) if r.scope == "domestic"]
            self.index.chain_cpi(session, domestic, chain_start, chain_end)
            # Curves for the published as-of day (UI booking-window chart).
            self.realtime.publish_curves(session, chain_end)
            # Also refresh curves for the collection day if different.
            if day != chain_end:
                self.realtime.publish_curves(session, day)
        finally:
            if session_browser is not None:
                session_browser.stop()
            session.close()

        return summary

    def _collect_one(
        self,
        session: Session,
        route,
        source: Source,
        job: ScrapeJob,
        allow_live: bool,
        browser: BrowserSession | None,
    ) -> tuple[int, str, str | None]:
        raws = []
        mode = "fixture"
        err = None
        live_source = source
        try:
            want_live = allow_live and (
                (source.airline_code and source.airline_code in _live_codes() and source.can_enter_cpi)
                or (source.id in _MARKET_SOURCE_IDS and _live_market())
            )
            if want_live:
                # Temporarily treat as HTTP-enabled for hub routing.
                live_source = Source(
                    id=source.id,
                    name=source.name,
                    type=source.type,
                    airline_code=source.airline_code,
                    collection_method=source.collection_method,
                    adapter=source.adapter,
                    enabled=source.enabled,
                    priority=source.priority,
                    can_enter_cpi=source.can_enter_cpi,
                    allow_http=True,
                    health=source.health,
                    note=source.note,
                )
                adapter = self.hub.adapter_for(live_source)
                if browser is not None and hasattr(adapter, "session"):
                    adapter.session = browser
                raws = adapter.search_fares(job)
                mode = "live"
                self._mark_health(session, source.id, "HEALTHY")
            else:
                raws = FixtureAdapter(source.id, source.airline_code or "6E").search_fares(job)
                mode = "fixture"
        except LiveCollectionError as exc:
            err = str(exc)
            log.warning("live failed %s %s: %s — fixture fallback", source.id, route.id, exc)
            self._mark_health(session, source.id, "DEGRADED")
            raws = FixtureAdapter(source.id, source.airline_code or "6E").search_fares(job)
            mode = "fixture"
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
            log.warning("collect failed %s %s: %s", source.id, route.id, exc)
            try:
                raws = FixtureAdapter(source.id, source.airline_code or "6E").search_fares(job)
                mode = "fixture"
            except Exception as exc2:  # noqa: BLE001
                return 0, "failed", f"{err} | fallback {exc2}"

        stored = 0
        for raw in raws:
            raw_id = self.raw.persist(session, raw, self.parser_version)
            canonical = self.normalizer.canonicalize(raw_id, raw)
            matched = self.identity.match(canonical)
            validated = self.quality.evaluate(matched)
            row = self.sampling.to_row(validated, live_source if mode == "live" else source, route)
            # Tag live rows via fare family note in quality path already; collection is in raw payload.
            session.merge(row)
            stored += 1
        return stored, mode, err

    def _mark_health(self, session: Session, source_id: str, health: str) -> None:
        row = session.get(SourceRow, source_id)
        if row is not None:
            row.health = health
            session.merge(row)
