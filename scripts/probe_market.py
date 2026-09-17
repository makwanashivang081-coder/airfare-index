"""Probe market sites (Ixigo, Skyscanner, MMT) for loadable public fares.

Run: python scripts/probe_market.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from apix.collectors.live.browser import BrowserSession, assert_no_bot_wall, goto
from apix.collectors.live.errors import BotWallError

OUT = Path(__file__).resolve().parent.parent / "data" / "probe" / "market"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dep = date.today() + timedelta(days=21)
    dep_iso = dep.isoformat()
    dep_sky = dep.strftime("%y%m%d")
    dep_mmt = dep.strftime("%d/%m/%Y")
    targets = {
        "ixigo": (
            "https://www.ixigo.com/search/result/flight"
            f"?from=DEL&to=BOM&date={dep_iso}&adults=1&children=0&infants=0&class=e"
        ),
        "skyscanner": (
            f"https://www.skyscanner.co.in/transport/flights/del/bom/{dep_sky}/"
            "?adults=1&cabinclass=economy&rtn=0"
        ),
        "mmt": (
            "https://www.makemytrip.com/flight/search"
            f"?itinerary=DEL-BOM-{dep_mmt}&tripType=O&paxType=A-1_C-0_I-0&cabinClass=E"
        ),
    }
    results: dict = {}
    with BrowserSession(headless=True) as session:
        for name, url in targets.items():
            print(f"=== {name} ===")
            try:
                with session.page() as (page, responses):
                    status = goto(page, url)
                    page.wait_for_timeout(10000)
                    wall = None
                    try:
                        assert_no_bot_wall(page, page.url)
                    except BotWallError as exc:
                        wall = str(exc)
                    html = page.content() or ""
                    try:
                        text = page.inner_text("body") or ""
                    except Exception:  # noqa: BLE001
                        text = ""
                    page.screenshot(path=str(OUT / f"{name}.png"))
                    (OUT / f"{name}.html").write_text(html[:250_000], encoding="utf-8")
                    results[name] = {
                        "status": status,
                        "final_url": page.url,
                        "wall": wall,
                        "rupee_marks": html.count("₹") + text.count("₹"),
                        "title": page.title(),
                        "json_responses": len(responses),
                        "text_snip": " ".join(text.split())[:400],
                    }
                    print(json.dumps(results[name], indent=2)[:600])
            except Exception as exc:  # noqa: BLE001
                results[name] = {"error": str(exc)}
                print("ERR", exc)
    (OUT / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"wrote {OUT / 'summary.json'}")


if __name__ == "__main__":
    main()
