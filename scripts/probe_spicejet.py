"""Drive the SpiceJet search form step by step and screenshot each stage.

Run: python scripts/probe_spicejet.py --dest BOM --days 21
Artifacts land in data/probe/spicejet_flow/.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from apix.collectors.live.browser import BrowserSession, goto

OUT = Path(__file__).resolve().parent.parent / "data" / "probe" / "spicejet_flow"

ORIGIN_INPUT = "input.css-1cwyjr8.r-homxoj.r-ubezar.r-10paoce.r-13qz1uu"


def shot(page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    print(f"  shot -> {name}.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", default="DEL")
    parser.add_argument("--dest", default="BOM")
    parser.add_argument("--days", type=int, default=21)
    parser.add_argument("--headful", action="store_true")
    args = parser.parse_args()

    target = date.today() + timedelta(days=args.days)
    OUT.mkdir(parents=True, exist_ok=True)

    with BrowserSession(headless=not args.headful) as session:
        with session.page() as (page, responses):
            print("1. loading homepage")
            goto(page, "https://www.spicejet.com/")
            page.wait_for_timeout(6000)
            shot(page, "01_home")

            fields = page.query_selector_all(ORIGIN_INPUT)
            print(f"   found {len(fields)} route inputs")
            if len(fields) < 2:
                print("   !! expected 2 route inputs (origin, destination)")
                return

            print(f"2. typing origin {args.origin}")
            fields[0].click()
            page.wait_for_timeout(1200)
            fields[0].fill("")
            page.keyboard.type(args.origin, delay=180)
            page.wait_for_timeout(2500)
            shot(page, "02_origin_dropdown")

            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)
            shot(page, "03_origin_picked")

            print(f"3. typing destination {args.dest}")
            fields = page.query_selector_all(ORIGIN_INPUT)
            fields[1].click()
            page.wait_for_timeout(1200)
            page.keyboard.type(args.dest, delay=180)
            page.wait_for_timeout(2500)
            shot(page, "04_dest_dropdown")

            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)
            shot(page, "05_dest_picked")

            print(f"4. looking for date {target.isoformat()}")
            day_label = target.strftime("%d %B %Y").lstrip("0")
            candidates = page.query_selector_all(f'[aria-label*="{target.day}"]')
            print(f"   aria candidates for day {target.day}: {len(candidates)}")
            shot(page, "06_before_date")

            print("5. dumping state")
            (OUT / "responses.json").write_text(
                json.dumps(
                    [{"url": r.url, "status": r.status, "bytes": len(r.body)} for r in responses],
                    indent=2,
                ),
                encoding="utf-8",
            )
            (OUT / "page.html").write_text(page.content(), encoding="utf-8")
            print(f"   url now: {page.url}")
            print(f"   json calls: {len(responses)}")
            print(f"   target day label would be: {day_label}")


if __name__ == "__main__":
    main()
