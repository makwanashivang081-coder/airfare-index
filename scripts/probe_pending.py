"""Probe remaining airline sites for loadable public fares.

Run: python scripts/probe_pending.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from apix.collectors.live.browser import BrowserSession, assert_no_bot_wall, goto
from apix.collectors.live.errors import BotWallError

OUT = Path(__file__).resolve().parent.parent / "data" / "probe" / "pending"
PRICE_RE = re.compile(r"(?:₹|INR|Rs\.?)\s*([0-9][0-9,]{2,})")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dep = date.today() + timedelta(days=21)
    ddmmyyyy = dep.strftime("%d%m%Y")
    iso = dep.isoformat()
    targets = {
        "air_india_home": "https://www.airindia.com/",
        "air_india_search": (
            "https://www.airindia.com/in/en/book/flight-search.html"
            f"?tripType=O&origin=DEL&destination=BOM&departureDate={iso}&adults=1&cabin=ECONOMY"
        ),
        "akasa_home": "https://www.akasaair.com/",
        "akasa_book": "https://www.akasaair.com/book-a-flight",
        "vistara_home": "https://www.airvistara.com/",
        "vistara_ai": "https://www.airindia.com/in/en/",  # Vistara merged into AI brand
        "mmt_home": "https://www.makemytrip.com/flights/",
        "cleartrip": (
            f"https://www.cleartrip.com/flights/results?from=DEL&to=BOM"
            f"&depart_date={iso}&adults=1&childs=0&infants=0&class=Economy&intl=n"
        ),
    }
    summary: dict = {}
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
                    prices = sorted(
                        {
                            float(m.replace(",", ""))
                            for m in PRICE_RE.findall(html + " " + text)
                            if 2500 <= float(m.replace(",", "")) <= 80000
                        }
                    )[:15]
                    page.screenshot(path=str(OUT / f"{name}.png"))
                    (OUT / f"{name}.html").write_text(html[:200_000], encoding="utf-8")
                    summary[name] = {
                        "status": status,
                        "final_url": page.url,
                        "wall": wall,
                        "rupees": (html + text).count("₹"),
                        "prices": prices,
                        "json": len(responses),
                        "title": page.title(),
                        "snip": " ".join(text.split())[:280],
                    }
                    print(json.dumps({k: summary[name][k] for k in summary[name] if k != "snip"}, indent=2)[:500])
                    print("snip:", summary[name]["snip"][:200])
            except Exception as exc:  # noqa: BLE001
                summary[name] = {"error": str(exc)}
                print("ERR", exc)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"wrote {OUT / 'summary.json'}")


if __name__ == "__main__":
    main()
