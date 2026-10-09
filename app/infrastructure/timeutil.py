from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    value = dt or utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def from_sim_seconds(base: datetime, seconds: float) -> str:
    from datetime import timedelta

    return iso(base + timedelta(seconds=float(seconds)))
