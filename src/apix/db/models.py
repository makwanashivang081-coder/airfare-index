from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from apix.db.session import Base


class AirportRow(Base):
    __tablename__ = "airports"
    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    city: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    country: Mapped[str] = mapped_column(String(8), default="IN")
    region: Mapped[str] = mapped_column(String(32))


class AirlineRow(Base):
    __tablename__ = "airlines"
    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))


class RouteRow(Base):
    __tablename__ = "routes"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    origin: Mapped[str] = mapped_column(String(8))
    destination: Mapped[str] = mapped_column(String(8))
    scope: Mapped[str] = mapped_column(String(16))
    region: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    cpi_weight: Mapped[float] = mapped_column(Float)
    market_weight: Mapped[float] = mapped_column(Float)


class SourceRow(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(16))
    airline_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    collection_method: Mapped[str] = mapped_column(String(24))
    adapter: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    can_enter_cpi: Mapped[int] = mapped_column(Integer, default=0)
    allow_http: Mapped[int] = mapped_column(Integer, default=0)
    health: Mapped[str] = mapped_column(String(16), default="HEALTHY")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class RawObservationRow(Base):
    __tablename__ = "raw_observations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(16))
    collected_at: Mapped[datetime] = mapped_column(DateTime)
    payload_json: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(String(255))
    parser_version: Mapped[str] = mapped_column(String(32))


class FareObservationRow(Base):
    __tablename__ = "fare_observations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    raw_id: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(16))
    origin: Mapped[str] = mapped_column(String(8))
    destination: Mapped[str] = mapped_column(String(8))
    airline_code: Mapped[str] = mapped_column(String(8))
    flight_number: Mapped[str] = mapped_column(String(16))
    departure_date: Mapped[date] = mapped_column(Date)
    collected_on: Mapped[date] = mapped_column(Date)
    advance_purchase_days: Mapped[int] = mapped_column(Integer)
    cabin: Mapped[str] = mapped_column(String(16))
    fare_family: Mapped[str] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(8))
    base_fare: Mapped[float] = mapped_column(Float)
    taxes: Mapped[float] = mapped_column(Float)
    total_price: Mapped[float] = mapped_column(Float)
    flight_id: Mapped[str] = mapped_column(String(64))
    fare_product_id: Mapped[str] = mapped_column(String(80))
    quality_status: Mapped[str] = mapped_column(String(24))
    quality_score: Mapped[float] = mapped_column(Float)
    can_enter_cpi: Mapped[int] = mapped_column(Integer)
    identity_confidence: Mapped[float] = mapped_column(Float)


class IndexPointRow(Base):
    __tablename__ = "index_points"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    series: Mapped[str] = mapped_column(String(16))
    level: Mapped[str] = mapped_column(String(24))
    key: Mapped[str] = mapped_column(String(32))
    period: Mapped[str] = mapped_column(String(16))
    value: Mapped[float] = mapped_column(Float)
    coverage: Mapped[float] = mapped_column(Float)
    n_obs: Mapped[int] = mapped_column(Integer)
    methodology_version: Mapped[str] = mapped_column(String(16))
    lineage_json: Mapped[str] = mapped_column(Text)


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime)
    actor: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text)
