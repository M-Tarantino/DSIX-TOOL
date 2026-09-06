import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import pipeline  # noqa: E402
from src.ingest import FeedItem  # noqa: E402
from src.store import JsonStore  # noqa: E402
from src.filters.base import FilterResult  # noqa: E402


class FakeProvider:
    """Stands in for a real LLM: confirms the one item that looks like an
    incident, rejects the other, so the test never needs network or an
    API key."""

    def extract(self, title, summary, source, url):
        if "ransomware" not in title.lower():
            return None
        return {
            "is_incident": True,
            "dimension": "cyber_security",
            "severity": "severe",
            "location": "Berlin",
            "date": "2026-09-01T00:00:00+00:00",
            "casualties": {"injured": None, "deaths": None},
            "summary": "A ransomware attack disrupted public administration systems.",
            "confidence": 0.9,
            "title": title,
        }


FAKE_ITEMS = [
    FeedItem(
        id="item-1",
        source="Test Wire",
        title="Ransomware attack hits city administration",
        link="https://example.test/1",
        summary="Attackers demanded payment after breaching municipal servers.",
        published="2026-09-01T00:00:00Z",
    ),
    FeedItem(
        id="item-2",
        source="Test Wire",
        title="Local football club wins regional cup",
        link="https://example.test/2",
        summary="Fans celebrated the club's first title in a decade.",
        published="2026-09-01T00:00:00Z",
    ),
]


def _fake_filter(title, summary):
    # Only the cyber-shaped headline should pass Stage 1.
    is_relevant = "ransomware" in title.lower()
    return FilterResult(is_relevant=is_relevant, dimension_guess="cyber_security" if is_relevant else None)


def test_pipeline_end_to_end_dry_run():
    with tempfile.TemporaryDirectory() as tmp:
        store = JsonStore(tmp)
        with patch("src.pipeline.ingest.fetch_all", return_value=FAKE_ITEMS), \
             patch("src.pipeline.get_filter", return_value=_fake_filter), \
             patch("src.pipeline.get_provider", return_value=FakeProvider()):
            score = pipeline.run(store=store)

        assert score["overall_score"] < 100  # the ransomware incident should move the needle
        assert score["dimensions"]["cyber_security"]["incidents_counted"] == 1

        incidents = store.load_incidents()
        assert len(incidents) == 1
        assert incidents[0]["dimension"] == "cyber_security"

        seen = store.load_seen_ids()
        assert "item-1" in seen and "item-2" in seen  # both marked seen, only one became an incident

        score_path = Path(tmp) / "score.json"
        history_path = Path(tmp) / "history.json"
        assert score_path.exists() and history_path.exists()


def test_pipeline_second_run_does_not_reprocess_seen_items():
    with tempfile.TemporaryDirectory() as tmp:
        store = JsonStore(tmp)
        with patch("src.pipeline.ingest.fetch_all", return_value=FAKE_ITEMS), \
             patch("src.pipeline.get_filter", return_value=_fake_filter), \
             patch("src.pipeline.get_provider", return_value=FakeProvider()):
            pipeline.run(store=store)
            # second run, same feed items -- nothing should be new
            pipeline.run(store=store)

        incidents = store.load_incidents()
        assert len(incidents) == 1  # not duplicated


def _run_all():
    tests = [obj for name, obj in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  ok  {test.__name__}")
    print(f"{len(tests)} pipeline tests passed")


if __name__ == "__main__":
    _run_all()
