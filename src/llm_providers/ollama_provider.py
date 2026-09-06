"""Stage 2 extraction via a local Ollama server -- no data leaves the machine.

This is the on-premise option: pair with FILTER_BACKEND=smollm for a fully
local pipeline (SmolLM for Stage 1, a larger local model here for Stage 2),
mirroring a client-filter + on-premise-processing split where the cloud
tier is never touched.

Requires a running Ollama instance (default http://localhost:11434) with
the target model pulled, e.g.: ollama pull qwen2.5:7b
"""
from __future__ import annotations

import json
import os
import re

import requests

from .base import EXTRACTION_SYSTEM_PROMPT
from .anthropic_provider import _parse_extraction  # shared JSON parsing


class OllamaProvider:
    def __init__(self, model: str | None = None):
        self.base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

    def extract(self, title: str, summary: str, source: str, url: str) -> dict | None:
        user_content = f"Headline: {title}\nSummary: {summary}\nSource: {source}"
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "stream": False,
            },
            timeout=60,
        )
        response.raise_for_status()
        text = response.json().get("message", {}).get("content", "")
        return _parse_extraction(text, title, source, url)
