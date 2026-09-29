"""UTC time helpers. All timestamps in Prospector are ISO 8601 UTC strings."""

from datetime import UTC, datetime


def utcnow_iso() -> str:
    """Current time as an ISO 8601 UTC string, e.g. ``2026-09-28T12:00:00Z``."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_utc_iso(value: str) -> str:
    """Normalize an ISO 8601 string with any offset to UTC.

    ``2026-09-28T08:00:00-04:00`` and ``2026-09-28T12:00:00Z`` both normalize
    to ``2026-09-28T12:00:00Z``.
    """
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def epoch_from_iso(value: str) -> int:
    """Unix epoch seconds (UTC) for an ISO 8601 string."""
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
