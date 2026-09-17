from __future__ import annotations

import random
import threading
import time
from urllib.parse import urlsplit


class HostThrottle:
    """Minimum spacing between requests to the same host, with jitter.

    Shared process-wide so two adapters pointed at one host cannot bypass each other.
    """

    _lock = threading.Lock()
    _last_call: dict[str, float] = {}

    def __init__(self, min_interval_s: float = 6.0, jitter_s: float = 3.0) -> None:
        self.min_interval_s = min_interval_s
        self.jitter_s = jitter_s

    def wait(self, url: str) -> None:
        host = urlsplit(url).netloc.lower()
        delay = self.min_interval_s + random.uniform(0.0, self.jitter_s)
        with self._lock:
            previous = self._last_call.get(host)
            now = time.monotonic()
            if previous is not None:
                remaining = (previous + delay) - now
                if remaining > 0:
                    time.sleep(remaining)
            self._last_call[host] = time.monotonic()
