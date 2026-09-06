"""End-to-end run: ingest -> filter -> extract -> score -> persist.

Usage:
    python -m src.pipeline

Reads config/feeds.json and config/scoring.json. Writes everything to
docs/data/ (the GitHub Pages root), so a scheduled run followed by a
git commit is the entire "deployment".
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from . import extract, ingest, scoring, synthesize
from .filters import get_filter
from .llm_providers import get_provider
from .store import JsonStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
FEEDS_CONFIG = ROOT / "config" / "feeds.json"
SCORING_CONFIG = ROOT / "config" / "scoring.json"
DATA_DIR = ROOT / "docs" / "data"


def run(store: JsonStore | None = None) -> dict:
    store = store or JsonStore(DATA_DIR)

    # 1. Ingest
    feeds = ingest.load_feed_config(FEEDS_CONFIG)
    all_items = ingest.fetch_all(feeds)
    seen_ids = store.load_seen_ids()
    fresh_items = ingest.dedupe(all_items, seen_ids)
    logger.info("Fetched %d items, %d new", len(all_items), len(fresh_items))

    # 2. Stage 1 filter
    stage1 = get_filter()
    filtered_items = []
    for item in fresh_items:
        result = stage1(item.title, item.summary)
        if result.is_relevant:
            filtered_items.append(item)
    logger.info("%d/%d items passed Stage 1 filter", len(filtered_items), len(fresh_items))

    # 3. Stage 2 extraction (only for what passed Stage 1)
    new_incidents: list[dict] = []
    if filtered_items:
        provider = get_provider()
        new_incidents = extract.extract_incidents(filtered_items, provider)
    logger.info("%d confirmed incidents extracted", len(new_incidents))

    # Mark ALL fresh items as seen (not just the ones that became incidents)
    # so noise doesn't get re-evaluated on every run.
    seen_ids.update(item.id for item in fresh_items)
    store.save_seen_ids(seen_ids)

    # Append new incidents to persistent storage
    if new_incidents:
        store.append_incidents(new_incidents)

    # 4. Rolling-window cleanup -- actually delete what's aged out, not just
    # ignore it at scoring time. Runs before scoring so incidents.json and
    # the score reflect the same window.
    config = scoring.load_scoring_config(SCORING_CONFIG)
    window_days = config["rolling_window_days"]
    all_incidents = store.prune_old_incidents(window_days)
    store.prune_old_history(window_days)
    logger.info("%d incidents in the %d-day rolling window after cleanup", len(all_incidents), window_days)

    # 5. Deterministic scoring
    score = scoring.compute_score(all_incidents, config)
    store.save_score(score)
    store.append_history(score)
    logger.info("DSIX score: %s (%s)", score["overall_score"], score["status"])

    # 6. Top-10 synthesis -- final output step
    top10 = synthesize.build_top10(all_incidents, config)
    store.save_top10(top10)
    logger.info("Top-10 synthesis written (%d items)", len(top10["items"]))

    return score


if __name__ == "__main__":
    run()
