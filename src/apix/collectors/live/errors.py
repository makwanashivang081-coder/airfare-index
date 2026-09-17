from __future__ import annotations

from apix.common.enums import QualityStatus
from apix.common.exceptions import ApixError


class LiveCollectionError(ApixError):
    """Base for anything that stops a live collection attempt."""

    quality_status: QualityStatus = QualityStatus.SCRAPE_FAILURE
    retryable: bool = False

    def __init__(self, message: str) -> None:
        super().__init__("LIVE_COLLECTION", message)


class RobotsDisallowedError(LiveCollectionError):
    """robots.txt forbids the path. We stop rather than proceed."""


class BotWallError(LiveCollectionError):
    """Captcha or bot interstitial. Never solved or bypassed — reported as a failed source."""


class NavigationError(LiveCollectionError):
    """Page did not load in time. Worth retrying."""

    retryable = True


class ParseError(LiveCollectionError):
    """Page loaded but the fare could not be located. Usually selector drift after a redesign."""


class NoFaresError(LiveCollectionError):
    """Page loaded and genuinely has no sellable fare. A real observation of absence, not a failure."""

    quality_status = QualityStatus.NOT_AVAILABLE
