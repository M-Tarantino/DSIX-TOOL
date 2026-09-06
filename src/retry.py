"""Exponential-backoff retry for Groq / Gemini API calls.

Both providers' Python SDKs raise different exception types for a rate
limit (Groq: `groq.RateLimitError`, a 429; Gemini's `google-genai` SDK:
a `google.genai.errors.ClientError`/`ServerError` carrying a 429/503
status, or `google.api_core.exceptions.ResourceExhausted` on the legacy
`google-generativeai` SDK). Rather than importing every SDK's exception
hierarchy here (and breaking if a provider changes its error classes),
this inspects the exception generically: a numeric `status_code` /
`code` attribute, or the string "429" / "rate limit" / "quota" /
"resource_exhausted" / "503" in the message. Retries only continue if
the failure looks transient; anything else (bad request, auth failure,
malformed response) is raised immediately since a retry cannot help.
"""
from __future__ import annotations

import functools
import logging
import random
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_TRANSIENT_MARKERS = ("429", "rate limit", "rate_limit", "quota", "resource_exhausted", "503", "overloaded")


def _looks_transient(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(status, int) and status in (429, 500, 502, 503, 504):
        return True
    text = str(exc).lower()
    return any(marker in text for marker in _TRANSIENT_MARKERS)


def with_backoff(
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry a callable with exponential backoff + jitter on transient
    (rate-limit / server-overload) errors only. Re-raises immediately on
    any non-transient error, and re-raises the last error once
    `max_retries` is exhausted.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001 - we re-inspect below
                    attempt += 1
                    if attempt > max_retries or not _looks_transient(exc):
                        raise
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    delay += random.uniform(0, delay * 0.25)  # jitter, avoid thundering herd
                    logger.warning(
                        "%s: transient error on attempt %d/%d (%s) -- retrying in %.1fs",
                        func.__qualname__, attempt, max_retries, exc, delay,
                    )
                    time.sleep(delay)

        return wrapper

    return decorator
