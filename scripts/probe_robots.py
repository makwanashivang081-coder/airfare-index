"""Report what each booking site's robots.txt allows for our collector.

Run: python scripts/probe_robots.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx

from apix.collectors.live.browser import DEFAULT_USER_AGENT
from apix.collectors.live.robots import RobotsPolicy

TARGETS: dict[str, list[str]] = {
    "IndiGo": [
        "https://www.goindigo.in/",
        "https://www.goindigo.in/book/flight-search.html",
        "https://www.goindigo.in/booking/flight-select.html",
    ],
    "Air India": [
        "https://www.airindia.com/",
        "https://www.airindia.com/in/en/book/flight-search.html",
    ],
    "SpiceJet": [
        "https://www.spicejet.com/",
        "https://www.spicejet.com/booking/select-flight",
    ],
    "Akasa Air": [
        "https://www.akasaair.com/",
        "https://www.akasaair.com/booking/select-flight",
    ],
    "MakeMyTrip": [
        "https://www.makemytrip.com/",
        "https://www.makemytrip.com/flight/search",
    ],
}


def main() -> None:
    policy = RobotsPolicy(DEFAULT_USER_AGENT)
    for name, urls in TARGETS.items():
        print(f"\n=== {name} ===")
        origin = urls[0]
        try:
            response = httpx.get(
                origin.rstrip("/") + "/robots.txt",
                timeout=15.0,
                headers={"User-Agent": DEFAULT_USER_AGENT},
                follow_redirects=True,
            )
            print(f"robots.txt HTTP {response.status_code}, {len(response.text)} bytes")
        except httpx.HTTPError as exc:
            print(f"robots.txt unreachable: {exc}")
            continue

        for url in urls:
            try:
                allowed = policy.allows(url)
                delay = policy.crawl_delay(url)
            except Exception as exc:  # noqa: BLE001 - probe should never crash the report
                print(f"  {url} -> error {exc}")
                continue
            verdict = "ALLOWED" if allowed else "DISALLOWED"
            suffix = f" (crawl-delay {delay}s)" if delay else ""
            print(f"  {verdict:10} {url}{suffix}")


if __name__ == "__main__":
    main()
