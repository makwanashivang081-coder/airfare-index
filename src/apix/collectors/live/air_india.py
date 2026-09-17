"""Air India live adapter — try airline site only. No Google proxy as airline live.

If the site blocks/times out, raise so the day job uses sample for SRC-AI.
Market live belongs under SRC-GFL (Google Flights), not under Air India.
"""

from __future__ import annotations

from apix.collectors.live.public_pages import AirIndiaPublicAdapter


class AirIndiaLiveAdapter(AirIndiaPublicAdapter):
    """Direct public page only. Fail closed → fixture. Never rewrite as Google proxy."""
