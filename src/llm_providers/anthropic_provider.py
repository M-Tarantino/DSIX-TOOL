"""Stage 2 extraction via the Anthropic API.

Requires ANTHROPIC_API_KEY. Model defaults to a small/cheap Claude model
since this runs on every filtered-in item -- override with ANTHROPIC_MODEL
if you want a stronger model for extraction quality.
"""
from __future__ import annotations

import json
import os
import re

from .base import EXTRACTION_SYSTEM_PROMPT


class AnthropicProvider:
    def __init__(self, model: str | None = None):
        import anthropic  # imported lazily so other providers don't need this dep

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    def extract(self, title: str, summary: str, source: str, url: str) -> dict | None:
        user_content = f"Headline: {title}\nSummary: {summary}\nSource: {source}"
        response = self.client.messages.create(
            model=self.model,
            max_tokens=400,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return _parse_extraction(text, title, source, url)


def _parse_extraction(text: str, title: str, source: str, url: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not parsed.get("is_incident"):
        return None
    parsed.setdefault("title", title)
    parsed["source"] = source
    parsed["url"] = url
    return parsed
