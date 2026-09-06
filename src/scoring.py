"""Deterministic DSIX-style scoring.

By design this module never calls an LLM. Extraction (Stage 2) turns
unstructured text into structured incidents; this module turns
structured incidents into a score, with plain arithmetic. That split
is what makes the score reproducible -- re-running against the same
incidents.json always yields the same number.

Method: each dimension starts at `baseline_score` (100 = fully stable)
and loses points per incident, weighted by severity and decayed
exponentially by age (recent incidents matter far more than old ones,
half-life configurable). The five dimension scores are then combined
by their configured weights into the overall index.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .dateutils import age_days


def load_scoring_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_score(incidents: list[dict], config: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    window_days = config["rolling_window_days"]
    half_life = config["decay_half_life_days"]
    baseline = config["baseline_score"]
    severity_points = config["severity_points"]
    dimensions = config["dimensions"]

    deductions = {dim: 0.0 for dim in dimensions}
    counted_incidents = {dim: 0 for dim in dimensions}

    for incident in incidents:
        dim = incident.get("dimension")
        if dim not in dimensions:
            continue
        age = age_days(incident.get("date"), now=now)
        if age < 0 or age > window_days:
            continue
        points = severity_points.get(incident.get("severity"), severity_points["minor"])
        decay = 0.5 ** (age / half_life)
        deductions[dim] += points * decay
        counted_incidents[dim] += 1

    dimension_scores = {}
    for dim, meta in dimensions.items():
        raw = baseline - deductions[dim]
        dimension_scores[dim] = {
            "label": meta["label"],
            "score": round(max(0.0, min(100.0, raw)), 1),
            "weight": meta["weight"],
            "incidents_counted": counted_incidents[dim],
        }

    overall = sum(dimension_scores[d]["score"] * dimensions[d]["weight"] for d in dimensions)
    overall = round(overall)

    return {
        "overall_score": overall,
        "status": _status_label(overall, config["status_bands"]),
        "computed_at": now.isoformat(),
        "window_days": window_days,
        "dimensions": dimension_scores,
    }


def _status_label(score: int, bands: list[dict]) -> str:
    for band in bands:
        if band["min"] <= score <= band["max"]:
            return band["label"]
    return "Unknown"
