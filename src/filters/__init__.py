import os
from typing import Callable

from .base import FilterResult
from . import keyword_filter


def get_filter() -> Callable[[str, str], FilterResult]:
    """Return the Stage 1 filter function selected via FILTER_BACKEND.

    FILTER_BACKEND=groq    (default) -- LLM gatekeeper via Groq, requires GROQ_API_KEY.
                                         Falls back to the keyword filter if a call fails.
    FILTER_BACKEND=keyword           -- no dependencies, zero cost, always available.
    FILTER_BACKEND=smollm            -- local model, see smollm_filter.py.
    """
    backend = os.environ.get("FILTER_BACKEND", "groq").lower()
    if backend == "smollm":
        from . import smollm_filter

        return smollm_filter.check
    if backend == "keyword":
        return keyword_filter.check
    from . import groq_filter

    return groq_filter.check
