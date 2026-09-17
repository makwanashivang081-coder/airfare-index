from __future__ import annotations

from apix.common.demo import demo_lock
from apix.common.config import settings


def phases_status() -> dict:
    lock = demo_lock()
    cfg = settings()
    return {
        "plan": "simple-v2",
        "live_data": lock["live_data"],
        "allow_live_http": bool(cfg.get("allow_live_http", False)),
        "phases": [
            {"id": "0", "name": "Message", "status": "completed", "note": "10-second story on home"},
            {"id": "1", "name": "Pretty demo", "status": "completed", "note": "Remapped UI/UX"},
            {"id": "2", "name": "Live SpiceJet", "status": "completed", "note": "SG collector + day pipeline"},
            {"id": "3", "name": "More airlines", "status": "completed", "note": "SG/QP direct live; 6E/AI/UK sample when blocked; market live on GFL/Ixigo/Cleartrip"},
            {"id": "4", "name": "Daily auto", "status": "completed", "note": "GitHub Actions run_live_day"},
            {"id": "5", "name": "SIH polish", "status": "completed", "note": "Judge demo script + honesty labels"},
        ],
        "one_liner": "Same 8 routes daily → one honest number → proof. Own scrapers. No captcha bypass.",
    }
