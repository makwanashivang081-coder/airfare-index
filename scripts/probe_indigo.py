"""Drive IndiGo search (deep-link first, homepage form fallback) and capture artifacts.

Run: python scripts/probe_indigo.py --origin DEL --dest BOM --days 21
Artifacts land in data/probe/indigo_flow/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from apix.collectors.live.browser import BrowserSession, assert_no_bot_wall, goto

OUT = Path(__file__).resolve().parent.parent / "data" / "probe" / "indigo_flow"

SEARCH_URL = (
    "https://www.goindigo.in/book/flight-search.html"
    "?from={origin}&to={destination}&departDate={depart}&adults=1&cabin=ECONOMY"
)


def shot(page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    print(f"  shot -> {name}.png")


def dump_state(page, responses, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}_responses.json").write_text(
        json.dumps(
            [{"url": r.url, "status": r.status, "bytes": len(r.body)} for r in responses],
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT / f"{name}_page.html").write_text(page.content(), encoding="utf-8")
    print(f"   url now: {page.url}")
    print(f"   json calls: {len(responses)}")


def try_deep_link(page, responses, origin: str, dest: str, target: date) -> bool:
    url = SEARCH_URL.format(origin=origin, destination=dest, depart=target.isoformat())
    print(f"1. deep-link {url}")
    goto(page, url)
    page.wait_for_timeout(8000)
    assert_no_bot_wall(page, page.url)
    shot(page, "01_deeplink")
    dump_state(page, responses, "01_deeplink")
    body = (page.inner_text("body") or "").lower()
    # Heuristic: results-ish page mentions price or flight numbers
    looks_like_results = ("₹" in (page.content() or "")) or ("6e" in body and "flight" in body)
    print(f"   looks_like_results={looks_like_results}")
    return looks_like_results


def try_homepage_form(page, responses, origin: str, dest: str, target: date) -> None:
    print("2. homepage form fallback")
    goto(page, "https://www.goindigo.in/")
    page.wait_for_timeout(5000)
    assert_no_bot_wall(page, page.url)
    shot(page, "02_home")

    # Common IndiGo booking widget patterns (best-effort; selectors drift)
    for selector in (
        'input[placeholder*="From"]',
        'input[name*="origin"]',
        'input[id*="origin"]',
        'input[aria-label*="From"]',
    ):
        loc = page.locator(selector)
        if loc.count() > 0:
            print(f"   origin field via {selector}")
            loc.first.click()
            page.wait_for_timeout(500)
            page.keyboard.type(origin, delay=120)
            page.wait_for_timeout(1200)
            page.keyboard.press("Enter")
            break

    for selector in (
        'input[placeholder*="To"]',
        'input[name*="destination"]',
        'input[id*="destination"]',
        'input[aria-label*="To"]',
    ):
        loc = page.locator(selector)
        if loc.count() > 0:
            print(f"   dest field via {selector}")
            loc.first.click()
            page.wait_for_timeout(500)
            page.keyboard.type(dest, delay=120)
            page.wait_for_timeout(1200)
            page.keyboard.press("Enter")
            break

    day_label = target.strftime("%d %B %Y").lstrip("0")
    by_label = page.locator(f'[aria-label*="{day_label}"]')
    if by_label.count() > 0:
        by_label.first.click()
        print(f"   picked date {day_label}")
    else:
        day = str(target.day)
        cells = page.locator(f'[aria-label*="{day}"]')
        if cells.count() > 0:
            cells.first.click()
            print(f"   picked day cell {day}")

    shot(page, "03_form_filled")
    clicked = False
    for label in ("Search Flight", "Search Flights", "Search", "Book"):
        btn = page.get_by_role("button", name=re.compile(label, re.I))
        if btn.count() > 0:
            btn.first.click()
            clicked = True
            print(f"   clicked {label}")
            break
    if not clicked:
        page.keyboard.press("Enter")
        print("   pressed Enter (no search button)")

    page.wait_for_timeout(10000)
    assert_no_bot_wall(page, page.url)
    shot(page, "04_after_search")
    dump_state(page, responses, "04_after_search")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", default="DEL")
    parser.add_argument("--dest", default="BOM")
    parser.add_argument("--days", type=int, default=21)
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--skip-form", action="store_true", help="Only try deep-link")
    args = parser.parse_args()

    target = date.today() + timedelta(days=args.days)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "meta.json").write_text(
        json.dumps(
            {
                "origin": args.origin.upper(),
                "destination": args.dest.upper(),
                "departure": target.isoformat(),
                "lead_days": args.days,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    from apix.collectors.live.errors import BotWallError, LiveCollectionError

    with BrowserSession(headless=not args.headful) as session:
        with session.page() as (page, responses):
            try:
                ok = try_deep_link(
                    page, responses, args.origin.upper(), args.dest.upper(), target
                )
            except (BotWallError, LiveCollectionError) as exc:
                print(f"deep-link blocked/failed: {exc}")
                try:
                    shot(page, "01_deeplink_blocked")
                    dump_state(page, responses, "01_deeplink_blocked")
                except Exception:  # noqa: BLE001
                    pass
                ok = False
            if not ok and not args.skip_form:
                try:
                    try_homepage_form(
                        page, responses, args.origin.upper(), args.dest.upper(), target
                    )
                except (BotWallError, LiveCollectionError) as exc:
                    print(f"homepage form blocked/failed: {exc}")
                    try:
                        shot(page, "04_form_blocked")
                        dump_state(page, responses, "04_form_blocked")
                    except Exception:  # noqa: BLE001
                        pass
            print(f"artifacts -> {OUT}")


if __name__ == "__main__":
    main()
