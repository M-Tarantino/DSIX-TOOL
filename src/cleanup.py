"""Cleanup old incidents outside the rolling window."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
INCIDENTS_FILE = ROOT / "docs" / "data" / "incidents.json"
WINDOW_DAYS = 90


def run():
    if not INCIDENTS_FILE.exists():
        logger.info("No incidents.json, skipping cleanup")
        return

    with open(INCIDENTS_FILE, "r", encoding="utf-8") as f:
        incidents = json.load(f)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=WINDOW_DAYS)

    before = len(incidents)
    cleaned = []

    for inc in incidents:
        try:
            date_str = inc.get("date", "")
            if not date_str:
                cleaned.append(inc)  # Keep if no date
                continue
            
            incident_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if incident_date.tzinfo is None:
                incident_date = incident_date.replace(tzinfo=timezone.utc)
            
            if incident_date >= cutoff:
                cleaned.append(inc)
        except (ValueError, TypeError):
            cleaned.append(inc)  # Keep if can't parse

    after = len(cleaned)
    removed = before - after

    with open(INCIDENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    logger.info(f"Cleanup: {before} → {after} incidents ({removed} removed)")


if __name__ == "__main__":
    run()