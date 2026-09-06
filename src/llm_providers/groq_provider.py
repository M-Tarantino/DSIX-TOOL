"""Stage 2 extraction via Groq API.

Unlimited free tier.
Requires GROQ_API_KEY from https://console.groq.com/

Model: llama-3.1-70b-versatile (top-tier speed + quality, no rate limiting)
"""
from __future__ import annotations

import json
import os
import re

from .base import EXTRACTION_SYSTEM_PROMPT
from .anthropic_provider import _parse_extraction  # shared JSON parsing
from ..retry import with_backoff


class GroqProvider:
    def __init__(self, model: str | None = None):
        from groq import Groq  # imported lazily

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        self.client = Groq(api_key=api_key)
        self.model = model or os.environ.get("GROQ_MODEL", "llama-3.1-70b-versatile")

    @with_backoff(max_retries=5, base_delay=2.0)
    def _call(self, user_content: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=400,
        )
        return response.choices[0].message.content or ""

    def extract(self, title: str, summary: str, source: str, url: str) -> dict | None:
        user_content = f"Headline: {title}\nSummary: {summary}\nSource: {source}"
        text = self._call(user_content)
        return _parse_extraction(text, title, source, url)

    @with_backoff(max_retries=5, base_delay=2.0)
    def generate_text(self, prompt: str) -> str:
        """Plain free-text completion -- used by src/synthesize.py for the
        Top-10 write-up, which is a writing task, not incident extraction.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        return response.choices[0].message.content or ""
