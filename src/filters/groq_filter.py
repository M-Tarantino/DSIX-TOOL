"""Stage 1 filter backed by Groq: the LLM gatekeeper.

Looks only at title + summary (cheap, no full-article fetch) and makes a
fast binary relevance call plus a best-effort dimension guess, so Stage 2
extraction only has to run on what actually looks like a genuine incident.
Deliberately over-inclusive on the "yes" side -- Stage 2 is the precision
layer -- but this still cuts most of the obviously-irrelevant volume
(sports, weather, entertainment, routine politics) before it reaches the
more expensive Stage 2 call.

Requires GROQ_API_KEY. Model default is a small/fast Groq model since this
runs on every single feed item -- override with GROQ_FILTER_MODEL.
"""
from __future__ import annotations

import json
import os
import re

from .base import FilterResult
from ..retry import with_backoff

_DIMENSIONS = [
    "terrorism_extremism",
    "cyber_security",
    "critical_infrastructure",
    "political_stability",
    "societal_safety",
]

_SYSTEM_PROMPT = f"""You are a fast relevance gatekeeper for a German national security \
monitor. Given a news headline and summary, decide only whether it PLAUSIBLY belongs to \
one of these dimensions -- you are not making the final call, Stage 2 will verify:

{", ".join(_DIMENSIONS)}

Favor false positives over false negatives: if in doubt, say relevant. Reject only what is \
clearly unrelated (sports, weather, entertainment, routine culture/lifestyle news, etc).

Reply with strict JSON only, nothing else:
{{"relevant": true|false, "dimension": "<one of the dimensions above, or null>", "confidence": <0.0-1.0>}}"""

_client = None


def _get_client():
    global _client
    if _client is None:
        from groq import Groq  # imported lazily so other filters don't need this dep

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set (required for FILTER_BACKEND=groq)")
        _client = Groq(api_key=api_key)
    return _client


@with_backoff(max_retries=5, base_delay=2.0)
def _call_groq(title: str, summary: str, model: str) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Headline: {title}\nSummary: {summary}"},
        ],
        max_tokens=100,
        temperature=0,
    )
    return response.choices[0].message.content or ""


def check(title: str, summary: str) -> FilterResult:
    model = os.environ.get("GROQ_FILTER_MODEL", "llama-3.1-8b-instant")
    try:
        text = _call_groq(title, summary, model)
    except Exception:  # noqa: BLE001 - a filter failure must not kill the run
        # Fail open onto the zero-dependency keyword filter rather than
        # silently dropping every item for the rest of the run.
        from . import keyword_filter

        return keyword_filter.check(title, summary)

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return FilterResult(is_relevant=False)
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return FilterResult(is_relevant=False)

    if not parsed.get("relevant"):
        return FilterResult(is_relevant=False)
    dimension = parsed.get("dimension")
    if dimension not in _DIMENSIONS:
        dimension = None
    confidence = parsed.get("confidence", 0.5)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.5
    return FilterResult(is_relevant=True, dimension_guess=dimension, confidence=confidence)
