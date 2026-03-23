"""Timezone utilities — all user-facing timestamps in IST (GMT+5:30)."""
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Current time in IST."""
    return datetime.now(IST)


def now_utc() -> datetime:
    """Current time in UTC (timezone-aware)."""
    return datetime.now(timezone.utc)


def to_ist(dt: datetime) -> datetime:
    """Convert any datetime to IST."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def format_ist(dt: datetime) -> str:
    """Format datetime as DD/MM/YYYY HH:MM IST."""
    ist_dt = to_ist(dt)
    return ist_dt.strftime("%d/%m/%Y %H:%M IST")


def format_ist_date(dt: datetime) -> str:
    """Format datetime as DD/MM/YYYY."""
    ist_dt = to_ist(dt)
    return ist_dt.strftime("%d/%m/%Y")


def parse_date_from_text(text: str) -> Optional[datetime]:
    """Try to extract a date from text like titles, filenames, etc.

    Handles: YYYY/MM/DD, YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY
    """
    # YYYY/MM/DD or YYYY-MM-DD
    m = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except ValueError:
            pass

    # DD/MM/YYYY or DD-MM-YYYY
    m = re.search(r"(\d{2})[/-](\d{2})[/-](\d{4})", text)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


def parse_iso(iso_str: str) -> Optional[datetime]:
    """Parse ISO 8601 string to timezone-aware datetime."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None
