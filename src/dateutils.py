"""Shared date parsing so scoring, storage pruning, and the backlog script
all agree on what "age in days" means for an incident.
"""
from __future__ import annotations

from datetime import datetime, timezone


def parse_date(date_str: str | None, fallback: datetime) -> datetime:
    """Best-effort ISO 8601 parse. Falls back (usually to `now`) on anything
    malformed so a bad LLM-provided date never crashes scoring or pruning --
    it just gets treated as "no age info", which the caller decides how to
    handle.
    """
    if not date_str:
        return fallback
    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError, AttributeError):
        return fallback


def age_days(date_str: str | None, now: datetime | None = None) -> float:
    """Age in days of `date_str` relative to `now`. Unparsable/missing dates
    are treated as age 0 (i.e. "just happened") -- this deliberately keeps
    them in the rolling window and in scoring rather than silently dropping
    or double-counting them as ancient.
    """
    now = now or datetime.now(timezone.utc)
    dt = parse_date(date_str, fallback=now)
    return (now - dt).total_seconds() / 86400
