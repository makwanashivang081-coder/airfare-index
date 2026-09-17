from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from playwright.sync_api import Page, Response, sync_playwright

from apix.common.logging import get_logger
from apix.collectors.live.errors import BotWallError, NavigationError

log = get_logger("apix.collectors.live.browser")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
)

BOT_WALL_MARKERS = (
    "captcha",
    "are you a human",
    "are you a person or a robot",
    "unusual traffic",
    "access denied",
    "request blocked",
    "verify you are human",
    "checking your browser",
    "akamfailoverpage",  # IndiGo / Akamai WAF failover
)

MAX_CAPTURED_BODY_CHARS = 400_000


@dataclass
class CapturedResponse:
    url: str
    status: int
    content_type: str
    body: str

    def as_json(self) -> Any | None:
        try:
            return json.loads(self.body)
        except (ValueError, TypeError):
            return None


@dataclass
class PageCapture:
    """Everything the page gave us, kept so a published fare can be traced back to its source."""

    url: str
    status: int
    html: str
    screenshot_png: bytes
    responses: list[CapturedResponse] = field(default_factory=list)

    def json_responses(self) -> list[CapturedResponse]:
        return [r for r in self.responses if r.as_json() is not None]

    def find_responses(self, *needles: str) -> list[CapturedResponse]:
        lowered = [n.lower() for n in needles]
        return [r for r in self.responses if any(n in r.url.lower() for n in lowered)]


class BrowserSession:
    """Owns one Chromium instance for the life of a collection run.

    Each job gets a fresh browser context, so cookies and storage from one airline never
    leak into the next, but we pay the browser launch cost only once.
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        user_agent: str = DEFAULT_USER_AGENT,
        locale: str = "en-IN",
        timezone_id: str = "Asia/Kolkata",
        nav_timeout_ms: int = 60_000,
    ) -> None:
        self.headless = headless
        self.user_agent = user_agent
        self.locale = locale
        self.timezone_id = timezone_id
        self.nav_timeout_ms = nav_timeout_ms
        self._pw = None
        self._browser = None

    def start(self) -> None:
        if self._browser is not None:
            return
        self._pw = sync_playwright().start()
        # disable-http2: some Indian booking CDNs (MMT/AI) break Playwright's default HTTP/2.
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=["--disable-http2", "--disable-features=Http2ServerPush"],
        )
        log.info("browser started headless=%s", self.headless)

    def stop(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._pw is not None:
            self._pw.stop()
            self._pw = None

    def __enter__(self) -> "BrowserSession":
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()

    @contextmanager
    def page(self) -> Iterator[tuple[Page, list[CapturedResponse]]]:
        self.start()
        assert self._browser is not None
        context = self._browser.new_context(
            user_agent=self.user_agent,
            locale=self.locale,
            timezone_id=self.timezone_id,
            viewport={"width": 1440, "height": 900},
        )
        context.set_default_navigation_timeout(self.nav_timeout_ms)
        context.set_default_timeout(self.nav_timeout_ms)
        page = context.new_page()
        captured: list[CapturedResponse] = []
        page.on("response", lambda response: _record(response, captured))
        try:
            yield page, captured
        finally:
            context.close()


def _record(response: Response, sink: list[CapturedResponse]) -> None:
    content_type = (response.headers or {}).get("content-type", "")
    if "json" not in content_type.lower():
        return
    try:
        body = response.text()
    except Exception:  # noqa: BLE001 - body may be gone once the page moves on
        return
    if len(body) > MAX_CAPTURED_BODY_CHARS:
        body = body[:MAX_CAPTURED_BODY_CHARS]
    sink.append(
        CapturedResponse(
            url=response.url,
            status=response.status,
            content_type=content_type,
            body=body,
        )
    )


def goto(page: Page, url: str, *, wait_until: str = "domcontentloaded") -> int:
    try:
        response = page.goto(url, wait_until=wait_until)
    except Exception as exc:  # noqa: BLE001 - playwright raises a broad family here
        raise NavigationError(f"{url} did not load: {exc}") from exc
    if response is None:
        raise NavigationError(f"{url} returned no response")
    return response.status


def assert_no_bot_wall(page: Page, url: str) -> None:
    """Detect an interstitial so we can report the source as blocked. We never try to solve one."""
    try:
        text = (page.title() or "") + " " + (page.inner_text("body") or "")
    except Exception:  # noqa: BLE001 - page may be mid-navigation
        return
    haystack = text[:4000].lower()
    for marker in BOT_WALL_MARKERS:
        if marker in haystack:
            raise BotWallError(f"{url} served a bot wall ({marker!r}). Source reported as blocked.")


def capture(page: Page, url: str, status: int, responses: list[CapturedResponse]) -> PageCapture:
    try:
        html = page.content()
    except Exception:  # noqa: BLE001
        html = ""
    try:
        screenshot = page.screenshot(full_page=False)
    except Exception:  # noqa: BLE001
        screenshot = b""
    return PageCapture(
        url=url,
        status=status,
        html=html,
        screenshot_png=screenshot,
        responses=list(responses),
    )
