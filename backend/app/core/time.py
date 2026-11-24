"""Time helpers. Store UTC; anchor business cutoffs to Asia/Dhaka (UTC+6)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DHAKA = ZoneInfo("Asia/Dhaka")


def now_utc() -> datetime:
    from app.core.security import utcnow

    return utcnow()


def as_utc(value: datetime) -> datetime:
    from datetime import UTC

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def dhaka_midnight_utc(day: date) -> datetime:
    from datetime import UTC

    local = datetime.combine(day, time.min, tzinfo=DHAKA)
    return local.astimezone(UTC)


def dhaka_tomorrow() -> date:
    return (datetime.now(DHAKA) + timedelta(days=1)).date()
