"""Stage 2 extraction via Google Gemini API.

Free tier: 60 requests/min, unlimited monthly.
Requires GOOGLE_API_KEY from https://ai.google.dev/

Model: gemini-1.5-flash (fast, cheap, good enough for extraction)
"""
from __future__ import annotations

import json
import os
import re

from .base import EXTRACTION_SYSTEM_PROMPT
from .anthropic_provider import _parse_extraction  # shared JSON parsing
from ..retry import with_backoff


class GeminiProvider:
    def __init__(self, model: str | None = None):
        import google.generativeai as genai  # imported lazily

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model or os.environ.get("GEMINI_MODEL", "gemini-flash-latest"))

    @with_backoff(max_retries=5, base_delay=3.0)
    def _call(self, user_content: str) -> str:
        response = self.model.generate_content(
            [
                {"role": "user", "parts": [EXTRACTION_SYSTEM_PROMPT]},
                {"role": "user", "parts": [user_content]},
            ]
        )
        return response.text or ""

    def extract(self, title: str, summary: str, source: str, url: str) -> dict | None:
        user_content = f"Headline: {title}\nSummary: {summary}\nSource: {source}"
        text = self._call(user_content)
        return _parse_extraction(text, title, source, url)

    @with_backoff(max_retries=5, base_delay=3.0)
    def generate_text(self, prompt: str) -> str:
        """Plain free-text completion -- used by src/synthesize.py for the
        Top-10 write-up, which is a writing task, not incident extraction.
        """
        response = self.model.generate_content(prompt)
        return response.text or ""
