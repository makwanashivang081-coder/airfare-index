from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from apix.collectors.hub import AdapterHub
from apix.common.config import methodology
from apix.common.logging import get_logger
from apix.common.time import each_date
from apix.db.models import FareObservationRow, IndexPointRow
from apix.db.session import Base, get_engine, get_session
from apix.identity.service import IdentityService
from apix.index.service import IndexService
from apix.master_data.service import MasterDataService
from apix.normalization.service import NormalizationService
from apix.orchestrator.service import Orchestrator
from apix.quality.service import QualityService
from apix.raw_data.service import RawDataService
from apix.realtime.service import RealtimeService
from apix.sampling.service import SamplingService
from apix.source_registry.service import SourceRegistryService

log = get_logger("apix.pipeline")


class Pipeline:
    """Collect → Normalize → Identify → Validate → Sample → Index. No scraper math."""

    def __init__(self) -> None:
        self.master = MasterDataService()
        self.registry = SourceRegistryService()
        self.orchestrator = Orchestrator()
        self.hub = AdapterHub()
        self.raw = RawDataService()
        self.normalizer = NormalizationService()
        self.identity = IdentityService()
        self.quality = QualityService()
        self.sampling = SamplingService()
        self.index = IndexService()
        self.realtime = RealtimeService()
        self.parser_version = str(methodology()["versions"]["parser"])

    def init_db(self) -> Session:
        Base.metadata.create_all(get_engine())
        session = get_session()
        self.master.seed(session)
        self.registry.seed(session)
        return session

    def collect_day(self, session: Session, collected_on: date, windows: list[int] | None = None) -> int:
        routes = [r for r in self.master.routes(session) if r.scope == "domestic"]
        sources = self.registry.collectors(session)
        jobs = self.orchestrator.plan_day(collected_on, routes, windows)
        stored = 0
        for job in jobs:
            route = self.master.require_route(session, job.origin, job.destination)
            for source in sources:
                raws = self.hub.execute(source, job)
                for raw in raws:
                    raw_id = self.raw.persist(session, raw, self.parser_version)
                    canonical = self.normalizer.canonicalize(raw_id, raw)
                    matched = self.identity.match(canonical)
                    validated = self.quality.evaluate(matched)
                    row = self.sampling.to_row(validated, source, route)
                    session.merge(row)
                    stored += 1
        session.commit()
        return stored

    def run(self, start: date, end: date, as_of: date) -> None:
        session = self.init_db()
        existing = session.query(FareObservationRow).count()
        if existing == 0:
            cpi_window = [int(methodology()["domestic"]["advance_purchase_days"])]
            log.info("collecting CPI window %s → %s", start, end)
            for day in each_date(start, end):
                self.collect_day(session, day, cpi_window)
            rt_start = date.fromordinal(max(start.toordinal(), as_of.toordinal() - 45))
            log.info("collecting realtime windows %s → %s", rt_start, as_of)
            windows = [int(x) for x in methodology()["realtime_windows"]]
            for day in each_date(rt_start, as_of):
                self.collect_day(session, day, windows)
        else:
            log.info("reusing %s observations", existing)
        session.query(IndexPointRow).delete()
        session.commit()
        domestic = [r for r in self.master.routes(session) if r.scope == "domestic"]
        self.index.chain_cpi(session, domestic, start, end)
        self.realtime.publish_curves(session, as_of)
        n = session.query(FareObservationRow).count()
        log.info("pipeline complete observations=%s", n)
        session.close()
