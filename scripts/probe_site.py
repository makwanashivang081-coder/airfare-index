"""Open a booking site and dump what it exposes, so an adapter can be written against reality.

Run: python scripts/probe_site.py <url> [--headful] [--wait SECONDS]
Artifacts land in data/probe/<host>/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from apix.collectors.live.browser import BrowserSession, goto

FIELD_SCRIPT = """
() => {
  const pick = (el) => ({
    tag: el.tagName.toLowerCase(),
    type: el.getAttribute('type'),
    id: el.id || null,
    name: el.getAttribute('name'),
    placeholder: el.getAttribute('placeholder'),
    aria: el.getAttribute('aria-label'),
    testid: el.getAttribute('data-testid') || el.getAttribute('data-test-id'),
    cls: (el.className || '').toString().slice(0, 120),
    text: (el.innerText || '').trim().slice(0, 80),
  });
  const inputs = Array.from(document.querySelectorAll('input,select')).map(pick);
  const buttons = Array.from(document.querySelectorAll('button,[role=button]')).slice(0, 60).map(pick);
  return { title: document.title, url: location.href, inputs, buttons };
}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--wait", type=float, default=8.0)
    args = parser.parse_args()

    host = urlsplit(args.url).netloc.replace(".", "_")
    out = Path(__file__).resolve().parent.parent / "data" / "probe" / host
    out.mkdir(parents=True, exist_ok=True)

    with BrowserSession(headless=not args.headful) as session:
        with session.page() as (page, responses):
            status = goto(page, args.url)
            page.wait_for_timeout(int(args.wait * 1000))

            info = page.evaluate(FIELD_SCRIPT)
            info["http_status"] = status

            (out / "fields.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
            (out / "page.html").write_text(page.content(), encoding="utf-8")
            page.screenshot(path=str(out / "page.png"), full_page=True)
            (out / "responses.json").write_text(
                json.dumps(
                    [{"url": r.url, "status": r.status, "bytes": len(r.body)} for r in responses],
                    indent=2,
                ),
                encoding="utf-8",
            )

            print(f"title      : {info['title']}")
            print(f"final url  : {info['url']}")
            print(f"http status: {status}")
            print(f"inputs     : {len(info['inputs'])}")
            print(f"buttons    : {len(info['buttons'])}")
            print(f"json calls : {len(responses)}")
            print(f"artifacts  : {out}")


if __name__ == "__main__":
    main()
