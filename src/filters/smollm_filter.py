"""Optional Stage 1 filter backed by a local small language model.

Mirrors the client-filtering stage of the zero-data-leak 3-tier pattern:
a tiny local model does binary relevance + coarse dimension detection
before anything reaches Stage 2's larger extractor. No article text
ever leaves the machine at this stage.

Requires: pip install -r requirements-smollm.txt
(transformers + torch -- deliberately kept out of the default
requirements.txt so the core pipeline stays lightweight in CI).

Enable with: FILTER_BACKEND=smollm
Model override: SMOLLM_MODEL (default: HuggingFaceTB/SmolLM2-135M-Instruct)
"""
from __future__ import annotations

import json
import os
import re

from .base import FilterResult

_DIMENSIONS = [
    "terrorism_extremism",
    "cyber_security",
    "critical_infrastructure",
    "political_stability",
    "societal_safety",
    "none",
]

_PROMPT_TEMPLATE = """Classify this news headline for a German national security monitor.
Dimensions: terrorism_extremism, cyber_security, critical_infrastructure, political_stability, societal_safety, none.

Headline: {title}
Summary: {summary}

Reply with strict JSON only: {{"relevant": true|false, "dimension": "<one of the dimensions above>"}}"""

_pipeline = None  # lazy-loaded singleton, one model load per process


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from transformers import pipeline  # noqa: PLC0415

        model_name = os.environ.get("SMOLLM_MODEL", "HuggingFaceTB/SmolLM2-135M-Instruct")
        _pipeline = pipeline("text-generation", model=model_name, max_new_tokens=60)
    return _pipeline


def check(title: str, summary: str) -> FilterResult:
    gen = _get_pipeline()
    prompt = _PROMPT_TEMPLATE.format(title=title[:200], summary=summary[:400])
    messages = [{"role": "user", "content": prompt}]
    output = gen(messages)[0]["generated_text"]
    reply = output[-1]["content"] if isinstance(output, list) else str(output)

    match = re.search(r"\{.*\}", reply, re.DOTALL)
    if not match:
        return FilterResult(is_relevant=False)
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return FilterResult(is_relevant=False)

    dimension = parsed.get("dimension")
    if dimension not in _DIMENSIONS or dimension == "none":
        return FilterResult(is_relevant=False)
    if not parsed.get("relevant"):
        return FilterResult(is_relevant=False)
    return FilterResult(is_relevant=True, dimension_guess=dimension, confidence=0.6)
