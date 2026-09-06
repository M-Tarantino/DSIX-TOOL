"""Stage 2 extraction via the OpenAI API (or any OpenAI-compatible endpoint).

Requires OPENAI_API_KEY. Set OPENAI_MODEL to whatever's currently the
cheapest/fastest model in your account -- not hardcoded here since that
changes over time. Set OPENAI_BASE_URL to point at a compatible endpoint
(e.g. a self-hosted OpenAI-API-compatible gateway) instead of OpenAI itself.
"""
from __future__ import annotations

import json
import os
import re

from .base import EXTRACTION_SYSTEM_PROMPT
from .anthropic_provider import _parse_extraction  # shared JSON parsing


class OpenAIProvider:
    def __init__(self, model: str | None = None):
        from openai import OpenAI  # imported lazily so other providers don't need this dep

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        base_url = os.environ.get("OPENAI_BASE_URL")  # None = default OpenAI endpoint
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def extract(self, title: str, summary: str, source: str, url: str) -> dict | None:
        user_content = f"Headline: {title}\nSummary: {summary}\nSource: {source}"
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=400,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        text = response.choices[0].message.content or ""
        return _parse_extraction(text, title, source, url)
