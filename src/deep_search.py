"""Deep security search via Groq + context search.

Runs every 12 hours. Searches for missed incidents in the last 14 days
using Groq with web context. Complements RSS crawling.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from .llm_providers import get_provider
from .store import JsonStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"

SEARCH_QUERIES = {
    "terrorism_extremism": [
        "Germany terrorist attack last 14 days",
        "Deutschland Anschlag Extremismus",
    ],
    "cyber_security": [
        "Germany cyberattack ransomware",
        "Deutschland Cyberangriff Hacker",
    ],
    "critical_infrastructure": [
        "Germany power grid outage",
        "Deutschland Stromausfall Infrastruktur",
    ],
    "political_stability": [
        "Germany government crisis",
        "Deutschland Regierung Krise",
    ],
    "societal_safety": [
        "Germany organized crime violence",
        "Deutschland Bandengewalt",
    ],
}


def run():
    store = JsonStore(DATA_DIR)
    provider = get_provider()
    
    logger.info("Starting deep security search...")
    
    existing = store.load_incidents()
    existing_ids = {inc.get("item_id") for inc in existing}
    
    new_incidents = []
    
    for dimension, queries in SEARCH_QUERIES.items():
        for query in queries:
            prompt = f"""Based on your knowledge, think about real security incidents in Germany 
from the past 14 days related to: {dimension} ({query})

List any REAL verified incidents you know about. For each, structure as JSON:
{{
  "dimension": "{dimension}",
  "severity": "minor|moderate|severe|critical",
  "title": "Incident title",
  "location": "German location or null",
  "date": "ISO 8601 date",
  "casualties": {{"injured": null, "deaths": null}},
  "summary": "One sentence, paraphrased",
  "source": "News source",
  "url": "https://example.com",
  "confidence": 0.7,
  "item_id": "deep-search-{dimension}-{len(new_incidents)}"
}}

Return ONLY valid JSON array, no other text."""
            
            logger.info(f"Searching: {dimension} - {query}")
            
            try:
                if hasattr(provider, 'generate_text'):
                    response = provider.generate_text(prompt)
                else:
                    logger.warning("Provider doesn't support generate_text, skipping")
                    continue
                
                # Parse JSON from response
                match = re.search(r'\[.*\]', response, re.DOTALL)
                if match:
                    incidents = json.loads(match.group(0))
                    for inc in incidents:
                        if inc.get("item_id") not in existing_ids:
                            new_incidents.append(inc)
                            existing_ids.add(inc.get("item_id"))
                            logger.info(f"Found: {inc.get('title')}")
            except Exception as e:
                logger.warning(f"Deep search failed for {dimension}: {e}")
                continue
    
    if new_incidents:
        store.append_incidents(new_incidents)
        logger.info(f"Added {len(new_incidents)} new incidents from deep search")
    else:
        logger.info("No new incidents from deep search")


if __name__ == "__main__":
    run()