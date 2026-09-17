from __future__ import annotations

import threading
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from apix.common.logging import get_logger

log = get_logger("apix.collectors.live.robots")

CACHE_TTL_S = 3600.0


class RobotsPolicy:
    """Fetches and caches robots.txt, and answers whether a URL may be collected.

    A host that does not serve robots.txt is treated as allowing collection, which is the
    behaviour the standard specifies. A host we cannot reach at all is treated as disallowed
    so that a network problem never looks like permission.
    """

    _lock = threading.Lock()
    _cache: dict[str, tuple[float, RobotFileParser | None]] = {}

    def __init__(self, user_agent: str, timeout_s: float = 10.0) -> None:
        self.user_agent = user_agent
        self.timeout_s = timeout_s

    def _parser_for(self, url: str) -> RobotFileParser | None:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        with self._lock:
            cached = self._cache.get(origin)
            if cached is not None and (time.monotonic() - cached[0]) < CACHE_TTL_S:
                return cached[1]

        parser: RobotFileParser | None
        try:
            response = httpx.get(
                f"{origin}/robots.txt",
                timeout=self.timeout_s,
                headers={"User-Agent": self.user_agent},
                follow_redirects=True,
            )
            if response.status_code == 404:
                parser = None
            elif response.status_code >= 400:
                parser = None
            else:
                parser = RobotFileParser()
                parser.parse(response.text.splitlines())
        except httpx.HTTPError as exc:
            log.warning("robots.txt unreachable for %s: %s", origin, exc)
            raise

        with self._lock:
            self._cache[origin] = (time.monotonic(), parser)
        return parser

    def allows(self, url: str) -> bool:
        try:
            parser = self._parser_for(url)
        except httpx.HTTPError:
            return False
        if parser is None:
            return True
        return parser.can_fetch(self.user_agent, url)

    def crawl_delay(self, url: str) -> float | None:
        try:
            parser = self._parser_for(url)
        except httpx.HTTPError:
            return None
        if parser is None:
            return None
        value = parser.crawl_delay(self.user_agent)
        return float(value) if value is not None else None
