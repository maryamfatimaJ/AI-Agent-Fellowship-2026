"""Timestamp helpers. Centralized so every component stamps time the same way."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def elapsed_seconds(start: datetime, end: datetime | None = None) -> float:
    end = end or utc_now()
    return round((end - start).total_seconds(), 3)
