from __future__ import annotations

import os
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from apix.analytics.briefing import build_callouts, events_payload, public_methodology
from apix.analytics.live_day import _inner_payload, is_live_payload, live_day_payload
from apix.analytics.phases import phases_status
from apix.analytics.proof import improvements_payload, proof_for_route
from apix.analytics.service import AnalyticsService
from apix.common.demo import as_of_date, demo_lock
from apix.common.enums import IndexLevel, SeriesType
from apix.common.logging import backend_root
from apix.common.time import iso_date, month_key
from apix.db.models import AirlineRow, AirportRow, FareObservationRow, IndexPointRow, RawObservationRow, RouteRow, SourceRow
from apix.db.session import database_backend, get_session
from apix.master_data.service import MasterDataService
from apix.pipeline import Pipeline
from apix.realtime.service import RealtimeService

AS_OF = as_of_date()
DASHBOARD = backend_root() / "dashboard"
app = FastAPI(title="AirPriceX APIx", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_ready = False


def _basket_cost_series(session: Session) -> tuple[list[dict], list[dict], float | None]:
    """Real median CPI-sample fares by day/month — money households actually face."""
    from sqlalchemy import func

    daily_rows = (
        session.query(
            FareObservationRow.collected_on,
            func.count().label("n"),
            func.avg(FareObservationRow.total_price).label("avg_price"),
        )
        .filter(FareObservationRow.can_enter_cpi == 1)
        .group_by(FareObservationRow.collected_on)
        .order_by(FareObservationRow.collected_on)
        .all()
    )
    cost_daily: list[dict] = []
    month_bucket: dict[str, list[float]] = {}
    for day, n, avg_price in daily_rows:
        if avg_price is None or n < 1:
            continue
        inr = round(float(avg_price), 0)
        period = day.isoformat()
        cost_daily.append({"period": period, "inr": inr, "n_obs": int(n)})
        mk = period[:7]
        month_bucket.setdefault(mk, []).append(inr)
    cost_monthly = [
        {"period": mk, "inr": round(sum(vals) / len(vals), 0), "n_obs": len(vals)}
        for mk, vals in sorted(month_bucket.items())
        if vals
    ]
    typical = cost_daily[-1]["inr"] if cost_daily else None
    return cost_daily, cost_monthly, typical


def _boot() -> Session:
    global _ready
    session = get_session()
    # Always refresh master data + source registry (SG/QP etc.) without wiping observations.
    MasterDataService().seed(session)
    from apix.source_registry.service import SourceRegistryService

    SourceRegistryService().seed(session)
    n = session.query(IndexPointRow).count()
    if n == 0:
        session.close()
        Pipeline().run(date(2026, 6, 1), AS_OF, AS_OF)
        session = get_session()
    _ready = True
    return session


@app.on_event("startup")
def startup() -> None:
    # Serverless is read-mostly. Never run the fixture collector on Vercel.
    if os.environ.get("VERCEL"):
        global _ready
        session = get_session()
        try:
            _ready = session.query(IndexPointRow).count() > 0
        finally:
            session.close()
        return
    _boot()


@app.get("/")
def home() -> FileResponse:
    return FileResponse(DASHBOARD / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/v1/health")
def health() -> dict:
    session = get_session()
    try:
        obs = session.query(FareObservationRow).count()
        idx = session.query(IndexPointRow).count()
        lock = demo_lock()
        return {
            "status": "ok",
            "observations": obs,
            "index_points": idx,
            "ready": _ready,
            "as_of": lock["as_of"],
            "collection_mode": lock["collection_mode"],
            "allow_live_http": lock["allow_live_http"],
            "live_data": lock["live_data"],
            "database_backend": database_backend(),
            "demo": lock,
        }
    finally:
        session.close()


@app.get("/api/v1/routes")
def routes() -> dict:
    session = get_session()
    try:
        rows = MasterDataService().routes(session)
        return {
            "routes": [
                {
                    "id": r.id,
                    "origin": r.origin,
                    "destination": r.destination,
                    "scope": r.scope,
                    "region": r.region,
                    "cpi_weight": r.cpi_weight,
                    "market_weight": r.market_weight,
                }
                for r in rows
            ]
        }
    finally:
        session.close()


@app.get("/api/v1/fares")
def fares(
    origin: str = Query(...),
    destination: str = Query(...),
    date: str = Query(AS_OF.isoformat()),
) -> dict:
    session = get_session()
    try:
        day = iso_date(date)
        rows = (
            session.query(FareObservationRow)
            .filter(
                FareObservationRow.origin == origin.upper(),
                FareObservationRow.destination == destination.upper(),
                FareObservationRow.collected_on == day,
            )
            .all()
        )
        sources = {row.id: row for row in session.query(SourceRow).all()}
        airlines = {row.code: row.name for row in session.query(AirlineRow).all()}
        raw_ids = {r.raw_id for r in rows}
        raws = {
            row.id: row
            for row in session.query(RawObservationRow).filter(RawObservationRow.id.in_(raw_ids)).all()
        } if raw_ids else {}
        fares_out = []
        for r in rows:
            inner = _inner_payload(raws.get(r.raw_id))
            live = is_live_payload(inner)
            fares_out.append(
                {
                    "id": r.id,
                    "source_id": r.source_id,
                    "source_name": sources[r.source_id].name if r.source_id in sources else r.source_id,
                    "source_type": sources[r.source_id].type if r.source_id in sources else None,
                    "airline": r.airline_code,
                    "airline_name": airlines.get(r.airline_code, r.airline_code),
                    "flight": r.flight_number,
                    "lead": r.advance_purchase_days,
                    "cabin": r.cabin,
                    "fare_family": r.fare_family,
                    "departure": r.departure_date.isoformat(),
                    "total": r.total_price,
                    "base": r.base_fare,
                    "taxes": r.taxes,
                    "quality": r.quality_status,
                    "quality_score": r.quality_score,
                    "can_enter_cpi": bool(r.can_enter_cpi),
                    "flight_id": r.flight_id,
                    "raw_id": r.raw_id,
                    "is_live": live,
                    "collection": "LIVE" if live else "SAMPLE",
                    "site": inner.get("site"),
                }
            )
        return {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "collected_on": day.isoformat(),
            "rule": {
                "cpi": "Airline source, economy, exact domestic T+21 (international T+60), quality not rejected. OTA cannot enter CPI.",
            },
            "fares": fares_out,
        }
    finally:
        session.close()


@app.get("/api/v1/live/day")
def live_day(date: str = Query(AS_OF.isoformat())) -> dict:
    session = get_session()
    try:
        return live_day_payload(session, iso_date(date))
    finally:
        session.close()


@app.get("/api/v1/index/current")
def index_current(date: str = Query(AS_OF.isoformat())) -> dict:
    session = get_session()
    try:
        analytics = AnalyticsService()
        day = iso_date(date)
        point = analytics.national(session, day.isoformat()) or analytics.national(session, month_key(day))
        if point is None:
            raise HTTPException(404, "Index not published for this period")
        hist = analytics.history(session, "national", "INDIA")
        month_pts = [h for h in hist if len(h.period) == 7]
        mom = None
        if len(month_pts) >= 2:
            last = month_pts[-1]
            prev = month_pts[-2]
            if prev.value > 0:
                mom = round((last.value / prev.value - 1) * 100, 1)
        yoy = None
        year_ago = f"{day.year - 1}-{day.month:02d}"
        prior_year = next((h for h in month_pts if h.period == year_ago), None)
        current_month = next((h for h in reversed(month_pts) if h.period.startswith(f"{day.year}-")), None)
        if prior_year is not None and current_month is not None and prior_year.value > 0:
            yoy = round((current_month.value / prior_year.value - 1) * 100, 1)
        coverage = analytics.coverage(session, day.isoformat())
        return {
            "index_name": "India Airfare Price Index",
            "base_year": 2024,
            "prototype_note": "CPI 2024 methods (Jevons + 21-day domestic). Prototype chained from first sample month = 100. Not official MoSPI CPI.",
            "index_value": round(point.value, 2),
            "period": point.period,
            "change_mom": mom,
            "change_yoy": yoy,
            "coverage": point.coverage,
            "confidence": "HIGH" if point.coverage >= 0.85 else "MEDIUM" if point.coverage >= 0.6 else "LOW",
            "observations": coverage["observations"],
            "cpi_observations": coverage["cpi_observations"],
            "sources_active": coverage["sources_active"],
            "methodology_version": point.methodology_version,
            "reading": (
                f"APIx {round(point.value, 2)} means the chained domestic T+21 economy sample "
                "is measured against the first complete prototype month = 100. "
                "It is not the official MoSPI CPI series."
            ),
        }
    finally:
        session.close()


@app.get("/api/v1/index/history")
def index_history(level: str = "national", key: str = "INDIA") -> dict:
    session = get_session()
    try:
        rows = AnalyticsService().history(session, level, key)
        return {
            "level": level,
            "key": key,
            "points": [
                {"period": r.period, "value": round(r.value, 2), "coverage": r.coverage, "n_obs": r.n_obs}
                for r in rows
                if len(r.period) == 10
            ],
        }
    finally:
        session.close()


@app.get("/api/v1/realtime/routes/{route_id}")
def realtime_route(route_id: str, date: str = Query(AS_OF.isoformat())) -> dict:
    session = get_session()
    try:
        origin, dest = route_id.upper().split("-")
        day = iso_date(date)
        curve = (
            session.query(IndexPointRow)
            .filter(
                IndexPointRow.series == "realtime",
                IndexPointRow.level == "route",
                IndexPointRow.period == day.isoformat(),
                IndexPointRow.key.like(f"{origin}-{dest}:T%"),
            )
            .all()
        )
        leads = []
        for row in curve:
            lead = int(row.key.split(":T")[-1])
            leads.append({"lead": lead, "price": round(row.value, 0), "n": row.n_obs})
        leads.sort(key=lambda x: x["lead"])
        current = next((x for x in leads if x["lead"] == 7), leads[0] if leads else None)
        vol = RealtimeService().volatility(session, f"{origin}-{dest}", day)
        return {
            "route_id": f"{origin}-{dest}",
            "collected_on": day.isoformat(),
            "current": current,
            "curve": leads,
            "volatility": vol,
        }
    finally:
        session.close()


@app.get("/api/v1/methodology")
def methodology_endpoint() -> dict:
    return public_methodology()


@app.get("/api/v1/phases")
def phases_endpoint() -> dict:
    return phases_status()


@app.get("/api/v1/proof/improvements")
def proof_improvements(date: str = Query(AS_OF.isoformat())) -> dict:
    session = get_session()
    try:
        day = iso_date(date)
        return {"as_of": day.isoformat(), "improvements": improvements_payload(session, day)}
    finally:
        session.close()


@app.get("/api/v1/proof/routes/{route_id}")
def proof_route(route_id: str, date: str = Query(AS_OF.isoformat())) -> dict:
    session = get_session()
    try:
        return proof_for_route(session, route_id, iso_date(date))
    finally:
        session.close()


@app.get("/api/v1/analytics/overview")
def overview(date: str = Query(AS_OF.isoformat())) -> dict:
    session = get_session()
    try:
        day = iso_date(date)
        idx = index_current(date=day.isoformat())
        airports = {row.code: row.city for row in session.query(AirportRow).all()}
        routes = session.query(RouteRow).filter(RouteRow.scope == "domestic", RouteRow.enabled == 1).all()
        market = []
        t7_prices: list[float] = []
        for route in routes:
            rt = realtime_route(f"{route.origin}-{route.destination}", date=day.isoformat())
            cpi_row = session.get(
                IndexPointRow,
                f"{SeriesType.CPI.value}:{IndexLevel.ROUTE.value}:{route.id}:{day.isoformat()}",
            )
            route_hist = [
                {"period": h.period, "value": round(h.value, 2)}
                for h in AnalyticsService().history(session, "route", route.id)
                if len(h.period) == 10
            ][-60:]
            current = rt.get("current")
            if current and current.get("price"):
                t7_prices.append(float(current["price"]))
            market.append(
                {
                    "id": route.id,
                    "origin": route.origin,
                    "destination": route.destination,
                    "origin_city": airports.get(route.origin, route.origin),
                    "destination_city": airports.get(route.destination, route.destination),
                    "region": route.region,
                    "label": f"{route.origin} → {route.destination}",
                    "cpi_weight": route.cpi_weight,
                    "market_weight": route.market_weight,
                    "current": current,
                    "volatility": rt.get("volatility"),
                    "curve": rt.get("curve"),
                    "index_history": route_hist,
                    "cpi_index": round(cpi_row.value, 2) if cpi_row is not None else None,
                }
            )
        regions = (
            session.query(IndexPointRow)
            .filter(
                IndexPointRow.series == "cpi",
                IndexPointRow.level == "region",
                IndexPointRow.period == day.isoformat(),
            )
            .all()
        )
        region_payload = [{"key": r.key, "value": round(r.value, 2), "n_obs": r.n_obs} for r in regions]
        sources = session.query(SourceRow).all()
        history = index_history()
        monthly = [
            {"period": r.period, "value": round(r.value, 2), "coverage": r.coverage, "n_obs": r.n_obs}
            for r in AnalyticsService().history(session, "national", "INDIA")
            if len(r.period) == 7
        ]
        events = events_payload(day.isoformat())
        method = public_methodology()
        t7_prices.sort()
        realtime_median = t7_prices[len(t7_prices) // 2] if t7_prices else None
        improvements = improvements_payload(session, day)
        proof = proof_for_route(session, "DEL-CCU", day)
        lock = demo_lock()
        live = live_day_payload(session, day)
        cost_daily, cost_monthly, typical_from_obs = _basket_cost_series(session)
        # Prefer real observed basket averages; fall back to index-scaled median.
        typical_ticket = typical_from_obs or (round(realtime_median, 0) if realtime_median else None)
        index_now = float(idx.get("index_value") or 0)
        if not cost_daily and realtime_median and index_now > 0:
            for row in history["points"][-90:]:
                if row.get("value") and row["value"] > 0:
                    cost_daily.append(
                        {
                            "period": row["period"],
                            "inr": round(realtime_median * (row["value"] / index_now), 0),
                            "n_obs": row.get("n_obs") or 0,
                        }
                    )
            for row in monthly:
                if row["value"] and row["value"] > 0:
                    cost_monthly.append(
                        {
                            "period": row["period"],
                            "inr": round(realtime_median * (row["value"] / index_now), 0),
                            "n_obs": row.get("n_obs") or 0,
                        }
                    )
        return {
            "as_of": day.isoformat(),
            "demo": lock,
            "index": idx,
            "realtime_median_t7": realtime_median,
            "typical_ticket_inr": typical_ticket,
            "cost_monthly": cost_monthly,
            "cost_daily": cost_daily[-60:],
            "market": market,
            "regions": region_payload,
            "events": events,
            "callouts": build_callouts(index=idx, regions=region_payload, events=events),
            "methodology": method,
            "monthly": monthly,
            "improvements": improvements,
            "proof": proof,
            "live": live,
            "phases": phases_status(),
            "sources": [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.type,
                    "health": s.health,
                    "can_enter_cpi": bool(s.can_enter_cpi),
                    "allow_http": bool(s.allow_http),
                    "collection_method": s.collection_method,
                    "enabled": bool(s.enabled),
                    "note": s.note,
                }
                for s in sources
            ],
            "history": history["points"][-60:],
        }
    finally:
        session.close()


app.mount("/assets", StaticFiles(directory=str(DASHBOARD / "assets")), name="assets")
