import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import scoring  # noqa: E402

NOW = datetime(2026, 9, 3, tzinfo=timezone.utc)

CONFIG = {
    "baseline_score": 100,
    "rolling_window_days": 90,
    "decay_half_life_days": 14,
    "dimensions": {
        "terrorism_extremism": {"label": "Terrorism & Extremism", "weight": 0.25},
        "cyber_security": {"label": "Cyber Security", "weight": 0.20},
        "critical_infrastructure": {"label": "Critical Infrastructure", "weight": 0.20},
        "political_stability": {"label": "Political Stability", "weight": 0.20},
        "societal_safety": {"label": "Societal Safety", "weight": 0.15},
    },
    "severity_points": {"minor": 3, "moderate": 8, "severe": 18, "critical": 35},
    "status_bands": [
        {"min": 80, "max": 100, "label": "Stable"},
        {"min": 60, "max": 79, "label": "Watchful"},
        {"min": 40, "max": 59, "label": "Elevated"},
        {"min": 20, "max": 39, "label": "High Alert"},
        {"min": 0, "max": 19, "label": "Crisis"},
    ],
}


def _incident(dimension, severity, days_ago):
    date = (NOW - timedelta(days=days_ago)).isoformat()
    return {"dimension": dimension, "severity": severity, "date": date}


def test_no_incidents_yields_baseline():
    result = scoring.compute_score([], CONFIG, now=NOW)
    assert result["overall_score"] == 100
    assert result["status"] == "Stable"


def test_critical_incident_today_drops_its_dimension():
    incidents = [_incident("cyber_security", "critical", days_ago=0)]
    result = scoring.compute_score(incidents, CONFIG, now=NOW)
    cyber = result["dimensions"]["cyber_security"]
    assert cyber["score"] == 65.0  # 100 - 35 points, zero decay at day 0
    assert cyber["incidents_counted"] == 1
    # untouched dimensions stay at baseline
    assert result["dimensions"]["political_stability"]["score"] == 100.0


def test_decay_softens_older_incidents():
    fresh = scoring.compute_score([_incident("cyber_security", "critical", 0)], CONFIG, now=NOW)
    half_life_old = scoring.compute_score([_incident("cyber_security", "critical", 14)], CONFIG, now=NOW)
    # at exactly one half-life, the deduction should be ~half of the fresh one
    fresh_deduction = 100 - fresh["dimensions"]["cyber_security"]["score"]
    aged_deduction = 100 - half_life_old["dimensions"]["cyber_security"]["score"]
    assert abs(aged_deduction - fresh_deduction / 2) < 0.2


def test_incidents_outside_window_are_excluded():
    incidents = [_incident("terrorism_extremism", "critical", days_ago=200)]
    result = scoring.compute_score(incidents, CONFIG, now=NOW)
    assert result["dimensions"]["terrorism_extremism"]["score"] == 100.0
    assert result["dimensions"]["terrorism_extremism"]["incidents_counted"] == 0


def test_weights_combine_correctly():
    # Force every dimension to a known score via one fresh critical incident each,
    # then hand-check the weighted sum.
    incidents = [
        _incident("terrorism_extremism", "critical", 0),  # -> 65.0, weight .25
        _incident("cyber_security", "moderate", 0),  # -> 92.0, weight .20
        _incident("critical_infrastructure", "severe", 0),  # -> 82.0, weight .20
        _incident("political_stability", "minor", 0),  # -> 97.0, weight .20
        _incident("societal_safety", "moderate", 0),  # -> 92.0, weight .15
    ]
    result = scoring.compute_score(incidents, CONFIG, now=NOW)
    expected = 65.0 * 0.25 + 92.0 * 0.20 + 82.0 * 0.20 + 97.0 * 0.20 + 92.0 * 0.15
    assert result["overall_score"] == round(expected)


def test_status_band_boundaries():
    assert scoring._status_label(31, CONFIG["status_bands"]) == "High Alert"
    assert scoring._status_label(20, CONFIG["status_bands"]) == "High Alert"
    assert scoring._status_label(19, CONFIG["status_bands"]) == "Crisis"
    assert scoring._status_label(80, CONFIG["status_bands"]) == "Stable"


def _run_all():
    tests = [obj for name, obj in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  ok  {test.__name__}")
    print(f"{len(tests)} scoring tests passed")


if __name__ == "__main__":
    _run_all()
