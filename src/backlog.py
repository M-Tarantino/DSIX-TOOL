"""One-time cold-start: retroactive backlog via Gemini + Google Search grounding.

The regular pipeline (src/pipeline.py) only ever sees incidents from the
moment it starts running the RSS feeds forward. This script is the
one-off exception: it asks Gemini, grounded in live Google Search results,
to reconstruct a retroactive ~60-day backlog of security-relevant events
in Germany so the dashboard isn't empty on day one.

Uses the `google-genai` SDK (not the legacy `google-generativeai` used by
src/llm_providers/gemini_provider.py) since Google Search grounding as a
model tool is only exposed there. Requires GOOGLE_API_KEY.

Usage:
    python -m src.backlog                  # skip if incidents.json is non-empty
    python -m src.backlog --force          # run even if incidents already exist
    python -m src.backlog --window-days 60 # override the backlog window
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from . import scoring, synthesize
from .extract import _VALID_DIMENSIONS, _VALID_SEVERITIES
from .retry import with_backoff
from .store import JsonStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
SCORING_CONFIG = ROOT / "config" / "scoring.json"
DATA_DIR = ROOT / "docs" / "data"

_DIMENSION_LIST = ", ".join(sorted(_VALID_DIMENSIONS))

_BACKLOG_PROMPT_TEMPLATE = """You are building a retroactive incident backlog for a German \
national security monitoring dashboard. Use Google Search to find genuine security-relevant \
events in Germany from the last {window_days} days, across these dimensions: {dimensions}.

For each incident you find, output one JSON object. Only include incidents you can verify \
via search results -- do not invent or guess. Aim for a comprehensive but not exhaustive \
backlog (roughly the most significant 20-40 events across the window, spread across all \
five dimensions where real events exist -- it is fine for a dimension to have few or no \
entries if nothing significant happened).

Respond with ONLY a JSON array, no other text, where each element has this exact shape:
{{
  "dimension": "<one of: {dimensions}>",
  "severity": "minor" | "moderate" | "severe" | "critical",
  "title": "<short headline, your own words>",
  "location": "<city/region or null>",
  "date": "<ISO 8601 date, YYYY-MM-DD>",
  "casualties": {{"injured": <int or null>, "deaths": <int or null>}},
  "summary": "<one or two sentences, in your own words, do not quote sources>",
  "source": "<publication or outlet name>",
  "url": "<source URL if available, else null>",
  "confidence": <0.0-1.0>
}}

Severity guide: minor = no injuries, localized; moderate = injuries or significant \
disruption; severe = many injured or major disruption; critical = deaths or \
national-scale impact."""


def _get_client():
    from google import genai  # imported lazily, only needed for this script

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set (required for the backlog script)")
    return genai.Client(api_key=api_key)


@with_backoff(max_retries=5, base_delay=5.0)
def _call_grounded_gemini(prompt: str, model: str) -> str:
    from google.genai import types  # imported lazily

    client = _get_client()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    return response.text or ""


def _is_valid(incident: dict) -> bool:
    return (
        incident.get("dimension") in _VALID_DIMENSIONS
        and incident.get("severity") in _VALID_SEVERITIES
        and isinstance(incident.get("title"), str)
        and incident.get("title")
        and isinstance(incident.get("summary"), str)
        and incident.get("summary")
    )


def generate_backlog(window_days: int = 60, model: str | None = None) -> list[dict]:
    model = model or os.environ.get("BACKLOG_MODEL", "gemini-2.5-flash")
    prompt = _BACKLOG_PROMPT_TEMPLATE.format(window_days=window_days, dimensions=_DIMENSION_LIST)
    text = _call_grounded_gemini(prompt, model)

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        logger.warning("Backlog generation returned no parseable JSON array")
        return []
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        logger.warning("Backlog JSON failed to parse: %s", exc)
        return []
    if not isinstance(parsed, list):
        return []

    incidents = [inc for inc in parsed if isinstance(inc, dict) and _is_valid(inc)]
    logger.info("Backlog: %d/%d candidate incidents passed validation", len(incidents), len(parsed))
    return incidents


def run(window_days: int = 60, force: bool = False, store: JsonStore | None = None) -> dict:
    store = store or JsonStore(DATA_DIR)

    existing = store.load_incidents()
    if existing and not force:
        logger.info(
            "incidents.json already has %d entries -- skipping backlog (use --force to re-run)",
            len(existing),
        )
        config = scoring.load_scoring_config(SCORING_CONFIG)
        return scoring.compute_score(existing, config)

    incidents = generate_backlog(window_days=window_days)
    if incidents:
        store.append_incidents(incidents)

    config = scoring.load_scoring_config(SCORING_CONFIG)
    all_incidents = store.prune_old_incidents(config["rolling_window_days"])
    score = scoring.compute_score(all_incidents, config)
    store.save_score(score)
    store.append_history(score)

    top10 = synthesize.build_top10(all_incidents, config)
    store.save_top10(top10)

    logger.info("Backlog seeded: %d incidents, DSIX score %s (%s)", len(all_incidents), score["overall_score"], score["status"])
    return score


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-days", type=int, default=60)
    parser.add_argument("--force", action="store_true", help="Run even if incidents.json is non-empty")
    args = parser.parse_args()
    run(window_days=args.window_days, force=args.force)
