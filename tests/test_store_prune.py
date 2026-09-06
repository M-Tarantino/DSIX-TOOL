import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.store import JsonStore  # noqa: E402

NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)


def _incident(days_ago, dim="cyber_security"):
    date = (NOW - timedelta(days=days_ago)).isoformat()
    return {"dimension": dim, "severity": "minor", "date": date, "title": f"item-{days_ago}"}


def test_prune_old_incidents_drops_only_out_of_window():
    with tempfile.TemporaryDirectory() as tmp:
        store = JsonStore(tmp)
        store.append_incidents([_incident(5), _incident(30), _incident(61), _incident(200)])

        kept = store.prune_old_incidents(window_days=60, now=NOW)

        kept_ages = {inc["title"] for inc in kept}
        assert kept_ages == {"item-5", "item-30"}
        # and the write actually persisted, not just the return value
        assert {inc["title"] for inc in store.load_incidents()} == {"item-5", "item-30"}


def test_prune_old_incidents_is_a_noop_when_nothing_expired():
    with tempfile.TemporaryDirectory() as tmp:
        store = JsonStore(tmp)
        store.append_incidents([_incident(1), _incident(2)])
        kept = store.prune_old_incidents(window_days=60, now=NOW)
        assert len(kept) == 2


def test_prune_old_history_uses_computed_at():
    with tempfile.TemporaryDirectory() as tmp:
        store = JsonStore(tmp)
        old = {"overall_score": 90, "computed_at": (NOW - timedelta(days=90)).isoformat()}
        recent = {"overall_score": 95, "computed_at": (NOW - timedelta(days=1)).isoformat()}
        store.append_history(old)
        store.append_history(recent)

        store.prune_old_history(window_days=60, now=NOW)

        history = store._read("history.json", [])
        assert len(history) == 1
        assert history[0]["overall_score"] == 95


def _run_all():
    tests = [obj for name, obj in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  ok  {test.__name__}")
    print(f"{len(tests)} store-prune tests passed")


if __name__ == "__main__":
    _run_all()
