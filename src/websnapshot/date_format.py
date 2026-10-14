"""Consistent human-readable dates in WebSnapshot.

Display format: YYYY.MM.DD HH:MM:SS (24-hour time).
Timezone-aware values are presented in UTC. Dates without a known time
remain date-only so that 00:00:00 is not fabricated.
Machine-readable timestamps in SQLite/JSON are never rewritten.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import re

DISPLAY_FORMAT = "%Y.%m.%d %H:%M:%S"
DATE_FORMAT = "%Y.%m.%d"

_PDF_DATE = re.compile(
    r"^D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?"
)
_DATE_ONLY = re.compile(r"^\d{4}[-./]\d{2}[-./]\d{2}$")
_DATE_WITH_TIME = re.compile(
    r"^(\d{4})\.(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?$"
)


def parse_timestamp(value: datetime | date | str | None) -> datetime | date | None:
    """Parse known timestamp forms without guessing from arbitrary text."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    source = value.strip()
    if not source:
        return None
    if _DATE_ONLY.fullmatch(source):
        try:
            return date.fromisoformat(source.replace(".", "-").replace("/", "-"))
        except ValueError:
            return None
    matched = _DATE_WITH_TIME.fullmatch(source)
    if matched:
        try:
            return datetime(
                int(matched[1]), int(matched[2]), int(matched[3]),
                int(matched[4]), int(matched[5]), int(matched[6] or 0),
            )
        except ValueError:
            return None
    match = _PDF_DATE.match(source)
    if match:
        try:
            return datetime(
                int(match[1]), int(match[2] or 1), int(match[3] or 1),
                int(match[4] or 0), int(match[5] or 0), int(match[6] or 0),
            )
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(source.replace("Z","+00:00"))
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(source)
    except (ValueError,TypeError,IndexError,OverflowError):
        return None


def format_datetime(value: datetime | date | str | None, *,
                    fallback: str = "–") -> str:
    """Render a recognised timestamp. Preserve unexpected metadata literally."""
    parsed=parse_timestamp(value)
    if parsed is None:
        if isinstance(value,str) and value.strip():
            return value
        return fallback
    if isinstance(parsed,datetime):
        if parsed.tzinfo is not None:
            parsed=parsed.astimezone(timezone.utc)
        return parsed.strftime(DISPLAY_FORMAT)
    # No time was supplied; showing midnight would incorrectly invent one.
    return parsed.strftime(DATE_FORMAT)


def format_property(key: str, value: object) -> str:
    """Apply date formatting only to explicitly date-typed document fields."""
    if key in {"created","modified","last_printed","examined_at",
               "last_modified","document_date","downloaded_at"}:
        return format_datetime(value)
    return str(value)
