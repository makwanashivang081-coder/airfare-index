from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_date(value: date | str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def add_days(value: date | str, days: int) -> date:
    return iso_date(value) + timedelta(days=days)


def days_between(start: date | str, end: date | str) -> int:
    return (iso_date(end) - iso_date(start)).days


def month_key(value: date | str) -> str:
    d = iso_date(value)
    return f"{d.year:04d}-{d.month:02d}"


def each_date(start: date | str, end: date | str) -> list[date]:
    cur = iso_date(start)
    last = iso_date(end)
    out: list[date] = []
    while cur <= last:
        out.append(cur)
        cur += timedelta(days=1)
    return out
