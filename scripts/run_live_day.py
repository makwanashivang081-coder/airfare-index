"""Run a live collection day for the 8-route basket.

  set ALLOW_LIVE_HTTP=true
  python scripts/run_live_day.py

Falls back to fixture per airline/route if blocked.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from apix.live.day_service import LiveDayService


def main() -> int:
    os.environ.setdefault("ALLOW_LIVE_HTTP", "true")
    summary = LiveDayService().run()
    out = Path("data/live/day_summary.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in summary if k != "details"}, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
