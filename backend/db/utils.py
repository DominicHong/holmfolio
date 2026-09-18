"""Database utilities."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Returns the current datetime in UTC."""
    return datetime.now(timezone.utc)
