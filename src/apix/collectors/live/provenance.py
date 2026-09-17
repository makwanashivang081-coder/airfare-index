from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from apix.collectors.live.browser import PageCapture
from apix.common.config import data_dir


@dataclass(frozen=True)
class ProvenanceRecord:
    """Where a published number physically came from."""

    artifact_dir: str
    html_sha256: str
    screenshot_sha256: str
    captured_url: str
    http_status: int
    json_response_count: int

    def as_payload(self) -> dict[str, object]:
        return {
            "artifact_dir": self.artifact_dir,
            "html_sha256": self.html_sha256,
            "screenshot_sha256": self.screenshot_sha256,
            "captured_url": self.captured_url,
            "http_status": self.http_status,
            "json_response_count": self.json_response_count,
        }


class ProvenanceStore:
    """Writes the captured page to disk so any fare can be audited back to what we actually saw."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or (data_dir() / "raw" / "live")

    def save(self, *, source_id: str, collected_on: date, key: str, capture: PageCapture) -> ProvenanceRecord:
        digest = hashlib.sha256(f"{source_id}:{collected_on}:{key}".encode()).hexdigest()[:16]
        target = self.root / source_id / collected_on.isoformat() / digest
        target.mkdir(parents=True, exist_ok=True)

        html_bytes = capture.html.encode("utf-8")
        (target / "page.html").write_bytes(html_bytes)
        if capture.screenshot_png:
            (target / "page.png").write_bytes(capture.screenshot_png)
        (target / "responses.json").write_text(
            json.dumps(
                [
                    {"url": r.url, "status": r.status, "content_type": r.content_type, "body": r.body}
                    for r in capture.responses
                ],
                indent=2,
            ),
            encoding="utf-8",
        )

        return ProvenanceRecord(
            artifact_dir=str(target.relative_to(data_dir())),
            html_sha256=hashlib.sha256(html_bytes).hexdigest(),
            screenshot_sha256=hashlib.sha256(capture.screenshot_png).hexdigest()
            if capture.screenshot_png
            else "",
            captured_url=capture.url,
            http_status=capture.status,
            json_response_count=len(capture.responses),
        )
