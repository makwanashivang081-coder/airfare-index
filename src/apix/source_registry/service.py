from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from apix.common.config import sources_config
from apix.common.enums import CollectionMethod, SourceStatus, SourceType
from apix.db.models import SourceRow


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    type: SourceType
    airline_code: str | None
    collection_method: CollectionMethod
    adapter: str | None
    enabled: bool
    priority: int
    can_enter_cpi: bool
    allow_http: bool
    health: SourceStatus
    note: str | None


def _row_to_source(row: SourceRow) -> Source:
    return Source(
        id=row.id,
        name=row.name,
        type=SourceType(row.type),
        airline_code=row.airline_code,
        collection_method=CollectionMethod(row.collection_method),
        adapter=row.adapter,
        enabled=bool(row.enabled),
        priority=row.priority,
        can_enter_cpi=bool(row.can_enter_cpi),
        allow_http=bool(row.allow_http),
        health=SourceStatus(row.health),
        note=row.note,
    )


class SourceRegistryService:
    def seed(self, session: Session) -> None:
        for item in sources_config()["sources"]:
            session.merge(
                SourceRow(
                    id=item["id"],
                    name=item["name"],
                    type=item["type"],
                    airline_code=item.get("airline_code"),
                    collection_method=item["collection_method"],
                    adapter=item.get("adapter"),
                    enabled=1 if item.get("enabled", True) else 0,
                    priority=int(item.get("priority", 5)),
                    can_enter_cpi=1 if item.get("can_enter_cpi") else 0,
                    allow_http=1 if item.get("allow_http") else 0,
                    health=item.get("health") or "HEALTHY",
                    note=item.get("note"),
                )
            )
        session.commit()

    def list_enabled(self, session: Session) -> list[Source]:
        rows = (
            session.query(SourceRow)
            .filter(SourceRow.enabled == 1)
            .order_by(SourceRow.priority)
            .all()
        )
        return [_row_to_source(r) for r in rows]

    def collectors(self, session: Session) -> list[Source]:
        return [
            s
            for s in self.list_enabled(session)
            if s.collection_method.value == "FIXTURE" and s.adapter
        ]
