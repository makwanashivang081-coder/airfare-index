from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from apix.collectors.base import RawFareObservation
from apix.common.config import data_dir
from apix.common.time import utc_now
from apix.db.models import AuditEventRow, RawObservationRow


class RawDataService:
    def __init__(self) -> None:
        self.root = data_dir() / "raw"
        self.root.mkdir(parents=True, exist_ok=True)

    def persist(self, session: Session, raw: RawFareObservation, parser_version: str) -> str:
        body = json.dumps({"query": raw.query, "payload": raw.payload}, sort_keys=True)
        digest = hashlib.sha256(f"{raw.source_id}:{raw.collected_on}:{body}".encode()).hexdigest()
        raw_id = digest[:32]
        storage_path = f"db://raw_observations/{raw_id}"
        session.merge(
            RawObservationRow(
                id=raw_id,
                source_id=raw.source_id,
                collected_at=utc_now(),
                payload_json=body,
                storage_path=storage_path,
                parser_version=parser_version,
            )
        )
        session.add(
            AuditEventRow(
                at=utc_now(),
                actor="raw_data",
                action="PERSIST",
                entity=raw_id,
                detail=raw.source_id,
            )
        )
        return raw_id
