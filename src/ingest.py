"""Fetch configured RSS/Atom feeds and return normalized, deduped items."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


@dataclass
class FeedItem:
    id: str
    source: str
    title: str
    link: str
    summary: str
    published: str  # ISO 8601 string, best-effort

    def to_dict(self) -> dict:
        return asdict(self)


def make_item_id(link: str, title: str) -> str:
    """Stable id independent of feed re-ordering or minor summary edits."""
    key = (link or title).strip().lower()
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def load_feed_config(path: str | Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["feeds"]


def fetch_all(feeds: list[dict], timeout: int = 15) -> list[FeedItem]:
    """Fetch every configured feed. A single feed failing does not abort the run."""
    import feedparser  # imported lazily so the rest of the package works without it

    items: list[FeedItem] = []
    for feed in feeds:
        try:
            parsed = feedparser.parse(feed["url"])
            if parsed.bozo and not parsed.entries:
                logger.warning("Feed %s failed to parse: %s", feed["id"], parsed.get("bozo_exception"))
                continue
            for entry in parsed.entries:
                link = entry.get("link", "")
                title = entry.get("title", "").strip()
                if not title:
                    continue
                summary = entry.get("summary", "") or entry.get("description", "")
                published = entry.get("published", "") or entry.get("updated", "")
                items.append(
                    FeedItem(
                        id=make_item_id(link, title),
                        source=feed["name"],
                        title=title,
                        link=link,
                        summary=summary,
                        published=published,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - one bad feed must not kill the run
            logger.warning("Feed %s raised %s", feed["id"], exc)
            continue
    return items


def dedupe(items: Iterable[FeedItem], seen_ids: set[str]) -> list[FeedItem]:
    fresh = [item for item in items if item.id not in seen_ids]
    return fresh
