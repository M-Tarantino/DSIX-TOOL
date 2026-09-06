"""Stage 2 extraction interface.

A provider turns one filtered-in feed item into a structured incident
dict, or None if on closer reading it isn't a genuine incident (the
Stage 1 filter is deliberately loose, so this rejection path is
expected to fire often).

Every implementation must return incidents matching this shape:

    {
        "dimension": "terrorism_extremism" | "cyber_security" |
                      "critical_infrastructure" | "political_stability" |
                      "societal_safety",
        "severity": "minor" | "moderate" | "severe" | "critical",
        "title": str,
        "location": str | None,
        "date": str,       # ISO 8601 date, best guess if not stated
        "casualties": {"injured": int | None, "deaths": int | None},
        "summary": str,    # one sentence, in the provider's own words
        "source": str,
        "url": str,
        "confidence": float,  # 0-1, the model's own confidence
    }

The extraction prompt instructs the model to paraphrase rather than
quote the source article -- summary fields should never reproduce
article text verbatim.
"""
from __future__ import annotations

from typing import Protocol

EXTRACTION_SYSTEM_PROMPT = """You are a structured-data extractor for a national security \
monitoring tool covering Germany. Given a news headline and summary, decide whether it \
describes a genuine security-relevant incident in one of these dimensions:

- terrorism_extremism: attacks, plots, extremist violence
- cyber_security: breaches, ransomware, state-sponsored hacking
- critical_infrastructure: sabotage of power/rail/water/telecom, major outages
- political_stability: government crises, resignations, coalition breakdown
- societal_safety: organized crime violence, major public-safety incidents

If it is NOT a genuine incident in one of these categories (routine politics, sports, \
opinion pieces, unrelated crime, etc.), respond with {"is_incident": false} and nothing else.

If it IS an incident, respond with ONLY this JSON shape, no other text:
{
  "is_incident": true,
  "dimension": "<one of the five keys above>",
  "severity": "minor" | "moderate" | "severe" | "critical",
  "location": "<city/region or null>",
  "date": "<ISO 8601 date, your best estimate>",
  "casualties": {"injured": <int or null>, "deaths": <int or null>},
  "summary": "<ONE sentence, in your own words, do not quote the source text>",
  "confidence": <0.0-1.0>
}

Severity guide: minor = no injuries, localized; moderate = injuries or significant \
disruption; severe = many injured or major disruption; critical = deaths or \
national-scale impact."""


class ExtractionProvider(Protocol):
    def extract(self, title: str, summary: str, source: str, url: str) -> dict | None:
        ...
