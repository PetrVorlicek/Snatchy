from datetime import datetime, timezone


def now() -> datetime:
    """Returns the current UTC time."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def make_utc(dt: datetime) -> datetime:
    """Converts a naive datetime to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
