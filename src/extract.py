"""Run Stage 2 extraction over a batch of filtered-in feed items.

Handles rate-limiting: processes 60 items per minute (Gemini free tier limit),
then waits 60 seconds before the next batch.
"""
from __future__ import annotations

import logging
import time

from .ingest import FeedItem
from .llm_providers.base import ExtractionProvider

logger = logging.getLogger(__name__)

_VALID_DIMENSIONS = {
    "terrorism_extremism",
    "cyber_security",
    "critical_infrastructure",
    "political_stability",
    "societal_safety",
}
_VALID_SEVERITIES = {"minor", "moderate", "severe", "critical"}

# Gemini free tier: 60 requests/min
# Process in batches of 60, wait 60 sec between batches
BATCH_SIZE = 60
BATCH_WAIT_SECONDS = 65  # 60 sec + 5 sec buffer


def extract_incidents(items: list[FeedItem], provider: ExtractionProvider) -> list[dict]:
    incidents: list[dict] = []
    
    for batch_idx in range(0, len(items), BATCH_SIZE):
        batch = items[batch_idx : batch_idx + BATCH_SIZE]
        batch_num = (batch_idx // BATCH_SIZE) + 1
        total_batches = (len(items) + BATCH_SIZE - 1) // BATCH_SIZE
        
        logger.info("Processing batch %d/%d (%d items)", batch_num, total_batches, len(batch))
        
        for item in batch:
            try:
                result = provider.extract(item.title, item.summary, item.source, item.link)
            except Exception as exc:  # noqa: BLE001 - one bad extraction must not kill the run
                logger.warning("Extraction failed for %s: %s", item.id, exc)
                continue
            if result is None:
                continue
            if not _is_valid(result):
                logger.warning("Provider returned malformed incident for %s, skipping", item.id)
                continue
            result["item_id"] = item.id
            incidents.append(result)
        
        # Wait before next batch (except after the last batch)
        if batch_idx + BATCH_SIZE < len(items):
            logger.info("Batch %d complete. Waiting %d seconds before next batch...", batch_num, BATCH_WAIT_SECONDS)
            time.sleep(BATCH_WAIT_SECONDS)
    
    return incidents


def _is_valid(incident: dict) -> bool:
    return (
        incident.get("dimension") in _VALID_DIMENSIONS
        and incident.get("severity") in _VALID_SEVERITIES
        and isinstance(incident.get("summary"), str)
        and incident.get("summary")
    )