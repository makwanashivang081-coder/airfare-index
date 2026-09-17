"""Run one live collection job (airline or market source).

Never bypasses captcha/bot walls. If blocked, exits non-zero with a clear reason.

  python scripts/collect_live.py --airline SG --origin DEL --dest BOM --lead 21
  python scripts/collect_live.py --airline QP --origin DEL --dest BOM --lead 21
  python scripts/collect_live.py --airline IXIGO --origin DEL --dest BOM --lead 21
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from apix.collectors.base import ScrapeJob
from apix.collectors.live.akasa import AkasaLiveAdapter
from apix.collectors.live.air_india import AirIndiaLiveAdapter
from apix.collectors.live.browser import BrowserSession
from apix.collectors.live.cleartrip import CleartripMarketAdapter
from apix.collectors.live.errors import BotWallError, LiveCollectionError, RobotsDisallowedError
from apix.collectors.live.google_flights import GoogleFlightsMarketAdapter
from apix.collectors.live.indigo import IndigoLiveAdapter
from apix.collectors.live.ixigo import IxigoMarketAdapter
from apix.collectors.live.spicejet import SpiceJetLiveAdapter
from apix.collectors.live.vistara import VistaraLiveAdapter
from apix.common.logging import get_logger

log = get_logger("apix.collect_live")

ADAPTERS = {
    "SG": ("SRC-SG", SpiceJetLiveAdapter),
    "6E": ("SRC-6E", IndigoLiveAdapter),
    "AI": ("SRC-AI", AirIndiaLiveAdapter),
    "QP": ("SRC-QP", AkasaLiveAdapter),
    "UK": ("SRC-UK", VistaraLiveAdapter),
    "IXIGO": ("SRC-IXIGO", IxigoMarketAdapter),
    "GFL": ("SRC-GFL", GoogleFlightsMarketAdapter),
    "CLEARTRIP": ("SRC-CLEARTRIP", CleartripMarketAdapter),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", default="DEL")
    parser.add_argument("--dest", default="BOM")
    parser.add_argument("--lead", type=int, default=21)
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--airline", default="SG", choices=sorted(ADAPTERS.keys()))
    args = parser.parse_args()

    os.environ.setdefault("ALLOW_LIVE_HTTP", "true")
    source_id, adapter_cls = ADAPTERS[args.airline.upper()]
    booking = date.today()
    departure = booking + timedelta(days=args.lead)
    job = ScrapeJob(
        job_id=f"LIVE-{args.origin}-{args.dest}-T{args.lead}",
        source_id=source_id,
        origin=args.origin.upper(),
        destination=args.dest.upper(),
        departure_date=departure,
        booking_date=booking,
        advance_purchase_days=args.lead,
        priority=1,
    )

    print(f"collecting {args.airline} {job.origin}->{job.destination} dep={departure} lead={args.lead}")
    print("rule: if captcha/bot-wall appears, we STOP (no bypass)")

    try:
        with BrowserSession(headless=not args.headful) as session:
            adapter = adapter_cls()
            adapter.session = session
            raws = adapter.search_fares(job)
    except RobotsDisallowedError as exc:
        print(f"BLOCKED by robots.txt: {exc}")
        return 2
    except BotWallError as exc:
        print(f"BLOCKED by bot wall/captcha: {exc}")
        print("Next step: try another public source/API, or keep fixture for that airline.")
        return 3
    except LiveCollectionError as exc:
        print(f"LIVE FAILED: {exc}")
        return 4

    out_dir = Path("data/live")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{args.airline}-{job.origin}-{job.destination}-T{args.lead}.json"
    payload = [
        {
            "source_id": r.source_id,
            "collected_on": r.collected_on.isoformat(),
            "query": r.query,
            "payload": r.payload,
        }
        for r in raws
    ]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"OK wrote {path}")
    for item in payload:
        print(f"  {item['payload'].get('flight')} {item['payload'].get('fare_inr')} site={item['payload'].get('site')}")
        if item["payload"].get("market_only"):
            print("  (market-only — not CPI)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
