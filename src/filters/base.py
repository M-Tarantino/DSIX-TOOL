"""Stage 1 filter interface.

A filter looks only at title + summary (cheap, no full-article fetch) and
decides whether an item is worth sending to the Stage 2 LLM extractor.
This is the expensive-call gatekeeper -- it should be fast and free
(or near-free) since it runs on every single feed item, whereas Stage 2
only runs on what passes here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class FilterResult:
    is_relevant: bool
    dimension_guess: str | None = None  # best-effort, Stage 2 confirms/corrects
    confidence: float = 0.0


class RelevanceFilter(Protocol):
    def check(self, title: str, summary: str) -> FilterResult:
        ...
