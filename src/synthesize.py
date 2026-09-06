"""Stage: regular Top-10 synthesis, the pipeline's final output step.

Ranking itself is deterministic and LLM-free (same severity/decay formula
as scoring.py, so "what's in the top 10" is reproducible and auditable).
Only the written synthesis paragraph -- a short, human-readable summary of
why these ten matter right now -- goes through an LLM, since that's the
one part that's genuinely a writing task rather than arithmetic. Written
in the provider's own words; the extraction stage already stripped out
source article text, so nothing here quotes the original reporting.

Provider is configurable via SYNTHESIS_PROVIDER (falls back to
LLM_PROVIDER, i.e. whatever Stage 2 is already using) since either Gemini
or Groq can write the summary -- this step doesn't need Gemini's search
grounding, just a writing pass over data DSIX already extracted.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from .dateutils import age_days

logger = logging.getLogger(__name__)

_SUMMARY_PROMPT_TEMPLATE = """You write a short German-language situation summary for a \
national security dashboard covering Germany. Below are the 10 most significant recent \
incidents (already structured, already scored -- do not invent details beyond what's given).

{items_block}

Write 2-4 sentences in German, in your own words, giving a reader a quick sense of what's \
driving the current security picture. Do not quote any incident's summary verbatim -- \
synthesize across them. No preamble, just the summary text."""


def _rank_top10(incidents: list[dict], scoring_config: dict, now: datetime) -> list[dict]:
    half_life = scoring_config["decay_half_life_days"]
    severity_points = scoring_config["severity_points"]
    window_days = scoring_config["rolling_window_days"]

    ranked = []
    for inc in incidents:
        age = age_days(inc.get("date"), now=now)
        if age < 0 or age > window_days:
            continue
        points = severity_points.get(inc.get("severity"), severity_points["minor"])
        weight = points * (0.5 ** (age / half_life))
        ranked.append((weight, inc))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    top = []
    for weight, inc in ranked[:10]:
        top.append(
            {
                "title": inc.get("title"),
                "dimension": inc.get("dimension"),
                "severity": inc.get("severity"),
                "location": inc.get("location"),
                "date": inc.get("date"),
                "summary": inc.get("summary"),
                "source": inc.get("source"),
                "url": inc.get("url"),
                "weight": round(weight, 2),
            }
        )
    return top


def _get_synthesis_provider():
    """Returns whichever provider SYNTHESIS_PROVIDER names (default: same
    backend as LLM_PROVIDER, i.e. Gemini unless overridden). Only Groq and
    Gemini implement `generate_text` since they're the two free options
    the architecture calls for here; anything else falls back below.
    """
    backend = (os.environ.get("SYNTHESIS_PROVIDER") or os.environ.get("LLM_PROVIDER", "gemini")).lower()
    if backend == "groq":
        from .llm_providers.groq_provider import GroqProvider

        return GroqProvider()
    from .llm_providers.gemini_provider import GeminiProvider

    return GeminiProvider()


def _write_synthesis(top10: list[dict]) -> str:
    if not top10:
        return "Keine sicherheitsrelevanten Vorfälle im aktuellen Zeitfenster erfasst."

    items_block = "\n".join(
        f"- [{item['dimension']}/{item['severity']}] {item['title']} "
        f"({item.get('location') or 'k.A.'}, {item.get('date') or 'k.A.'}): {item['summary']}"
        for item in top10
    )
    prompt = _SUMMARY_PROMPT_TEMPLATE.format(items_block=items_block)

    try:
        provider = _get_synthesis_provider()
        text = provider.generate_text(prompt).strip()
        if text:
            return text
    except Exception as exc:  # noqa: BLE001 - synthesis failing must not kill the run
        logger.warning("Top-10 synthesis LLM call failed: %s", exc)

    # Fallback: a plain, code-generated summary if the LLM call didn't
    # produce usable text (still fully deterministic and useful).
    dims = ", ".join(sorted({item["dimension"] for item in top10 if item.get("dimension")}))
    return f"Die {len(top10)} gewichtigsten Vorfälle im aktuellen Fenster betreffen: {dims}."


def build_top10(incidents: list[dict], scoring_config: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    top10 = _rank_top10(incidents, scoring_config, now)
    synthesis_text = _write_synthesis(top10)
    return {
        "generated_at": now.isoformat(),
        "synthesis_text": synthesis_text,
        "items": top10,
    }
