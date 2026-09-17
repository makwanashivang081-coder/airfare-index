from __future__ import annotations

from datetime import date

from apix.common.config import settings
from apix.common.exceptions import ConfigError
from apix.common.time import iso_date


def as_of_date() -> date:
    cfg = settings()
    raw = cfg.get("as_of")
    if not raw:
        raise ConfigError("settings.yaml missing as_of")
    return iso_date(str(raw))


def demo_lock() -> dict:
    cfg = settings()
    demo = cfg.get("demo") if isinstance(cfg.get("demo"), dict) else {}
    allow_live = bool(cfg.get("allow_live_http", False))
    mode = str(cfg.get("collection_mode") or "fixture")
    # Published live mix: either the API is live-scraping, or we shipped a day with live receipts.
    live = bool(demo.get("live_published")) or (allow_live and mode in {"live", "hybrid"})
    return {
        "as_of": as_of_date().isoformat(),
        "collection_mode": mode,
        "allow_live_http": allow_live,
        "live_data": live,
        "locked": bool(demo.get("locked", True)),
        "headline": str(demo.get("headline") or "Fixture prototype"),
        "story_route": str(demo.get("story_route") or "DEL-CCU"),
        "story": str(demo.get("story") or ""),
        "judge_path": str(demo.get("judge_path") or ""),
        "when_live": "Set demo.live_published after a legal live day is baked into data/apix.db.",
    }
