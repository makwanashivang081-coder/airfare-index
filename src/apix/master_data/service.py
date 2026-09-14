from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from apix.common.config import routes_config
from apix.db.models import AirlineRow, AirportRow, RouteRow

AIRPORTS: tuple[tuple[str, str, str, str, str], ...] = (
    ("DEL", "Delhi", "Indira Gandhi International", "IN", "north"),
    ("BOM", "Mumbai", "Chhatrapati Shivaji Maharaj", "IN", "west"),
    ("BLR", "Bengaluru", "Kempegowda International", "IN", "south"),
    ("CCU", "Kolkata", "Netaji Subhas Chandra Bose", "IN", "east"),
    ("HYD", "Hyderabad", "Rajiv Gandhi International", "IN", "south"),
    ("MAA", "Chennai", "Chennai International", "IN", "south"),
    ("DXB", "Dubai", "Dubai International", "AE", "gulf"),
)

AIRLINES: tuple[tuple[str, str], ...] = (
    ("6E", "IndiGo"),
    ("AI", "Air India"),
    ("UK", "Vistara"),
    ("IX", "Air India Express"),
    ("QP", "Akasa Air"),
    ("SG", "SpiceJet"),
)


@dataclass(frozen=True)
class Route:
    id: str
    origin: str
    destination: str
    scope: str
    region: str
    cpi_weight: float
    market_weight: float


class MasterDataService:
    def seed(self, session: Session) -> None:
        for code, city, name, country, region in AIRPORTS:
            session.merge(
                AirportRow(code=code, city=city, name=name, country=country, region=region)
            )
        for code, name in AIRLINES:
            session.merge(AirlineRow(code=code, name=name))
        cfg = routes_config()
        for row in cfg["members"]:
            rid = f"{row['origin']}-{row['destination']}"
            session.merge(
                RouteRow(
                    id=rid,
                    origin=row["origin"],
                    destination=row["destination"],
                    scope="domestic",
                    region=row["region"],
                    enabled=1,
                    cpi_weight=float(row["cpi_weight"]),
                    market_weight=float(row["market_weight"]),
                )
            )
        for row in cfg.get("international", {}).get("members", []):
            rid = f"{row['origin']}-{row['destination']}"
            session.merge(
                RouteRow(
                    id=rid,
                    origin=row["origin"],
                    destination=row["destination"],
                    scope="international",
                    region=row["region"],
                    enabled=1,
                    cpi_weight=float(row["cpi_weight"]),
                    market_weight=float(row["market_weight"]),
                )
            )
        session.commit()

    def routes(self, session: Session, scope: str | None = None) -> list[Route]:
        q = session.query(RouteRow).filter(RouteRow.enabled == 1)
        if scope:
            q = q.filter(RouteRow.scope == scope)
        return [
            Route(
                id=r.id,
                origin=r.origin,
                destination=r.destination,
                scope=r.scope,
                region=r.region,
                cpi_weight=r.cpi_weight,
                market_weight=r.market_weight,
            )
            for r in q.all()
        ]

    def require_route(self, session: Session, origin: str, destination: str) -> Route:
        rid = f"{origin}-{destination}"
        row = session.get(RouteRow, rid)
        if row is None or row.enabled != 1:
            raise KeyError(f"Route {rid} is not in the locked basket")
        return Route(
            id=row.id,
            origin=row.origin,
            destination=row.destination,
            scope=row.scope,
            region=row.region,
            cpi_weight=row.cpi_weight,
            market_weight=row.market_weight,
        )
