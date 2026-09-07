"""Rotate incidents at midnight: recent → history."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
INCIDENTS_FILE = DATA_DIR / "incidents.json"
RECENT_FILE = DATA_DIR / "incidents-recent.json"
HISTORY_FILE = DATA_DIR / "incidents-history.json"


def run():
    """Rotate incidents if we've crossed into a new day."""
    now = datetime.now(timezone.utc)
    
    # Check if rotation already happened today
    rotation_marker = DATA_DIR / ".rotation-date"
    today = now.strftime("%Y-%m-%d")
    
    if rotation_marker.exists():
        with open(rotation_marker, "r") as f:
            last_rotation = f.read().strip()
        if last_rotation == today:
            logger.info("Rotation already done today, skipping")
            return
    
    logger.info("Rotating incidents for new day...")
    
    # Load all incidents
    if not INCIDENTS_FILE.exists():
        logger.info("No incidents.json, nothing to rotate")
        return
    
    with open(INCIDENTS_FILE, "r", encoding="utf-8") as f:
        all_incidents = json.load(f)
    
    # Move current recent → history
    if RECENT_FILE.exists():
        with open(RECENT_FILE, "r", encoding="utf-8") as f:
            yesterday_recent = json.load(f)
        
        # Append yesterday's recent to history
        history = []
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        
        history.extend(yesterday_recent)
        
        # Keep only last 60 days in history
        cutoff = now - timedelta(days=60)
        filtered_history = []
        for inc in history:
            try:
                date_str = inc.get("date", "")
                if date_str:
                    incident_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if incident_date.tzinfo is None:
                        incident_date = incident_date.replace(tzinfo=timezone.utc)
                    if incident_date >= cutoff:
                        filtered_history.append(inc)
                else:
                    filtered_history.append(inc)
            except (ValueError, TypeError):
                filtered_history.append(inc)
        
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(filtered_history, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Moved {len(yesterday_recent)} incidents to history")
    
    # Current incidents → recent
    with open(RECENT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_incidents, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Set {len(all_incidents)} incidents as recent")
    
    # Mark rotation done
    with open(rotation_marker, "w") as f:
        f.write(today)
    
    logger.info("Rotation complete")


if __name__ == "__main__":
    run()