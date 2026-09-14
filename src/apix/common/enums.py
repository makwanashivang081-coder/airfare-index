from enum import Enum


class SourceType(str, Enum):
    AIRLINE = "AIRLINE"
    OTA = "OTA"
    REGULATOR = "REGULATOR"
    API = "API"


class SourceStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    DISABLED = "DISABLED"


class CollectionMethod(str, Enum):
    FIXTURE = "FIXTURE"
    HTTP = "HTTP"
    PLAYWRIGHT = "PLAYWRIGHT"
    MANUAL_DROP = "MANUAL_DROP"
    REFERENCE = "REFERENCE"


class Cabin(str, Enum):
    ECONOMY = "economy"
    BUSINESS = "business"


class QualityStatus(str, Enum):
    OBSERVED = "OBSERVED"
    MISSING = "MISSING"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    SOLD_OUT = "SOLD_OUT"
    INVALID = "INVALID"
    SCRAPE_FAILURE = "SCRAPE_FAILURE"
    DUPLICATE = "DUPLICATE"
    WARNING = "WARNING"


class SeriesType(str, Enum):
    CPI = "cpi"
    REALTIME = "realtime"


class IndexLevel(str, Enum):
    ROUTE = "route"
    REGION = "region"
    DOMESTIC = "domestic"
    INTERNATIONAL = "international"
    NATIONAL = "national"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
