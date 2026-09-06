import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.filters import keyword_filter  # noqa: E402


def test_cyber_headline_detected():
    result = keyword_filter.check(
        "Ransomware attack hits city administration",
        "Attackers demanded payment after a data breach of municipal servers.",
    )
    assert result.is_relevant
    assert result.dimension_guess == "cyber_security"


def test_infrastructure_headline_detected_german():
    result = keyword_filter.check(
        "Stromausfall nach Sabotage am Umspannwerk",
        "Ein Angriff auf das Stromnetz legte die Region lahm.",
    )
    assert result.is_relevant
    assert result.dimension_guess == "critical_infrastructure"


def test_irrelevant_headline_ignored():
    result = keyword_filter.check(
        "Local football club wins regional cup",
        "Fans celebrated the club's first title in a decade.",
    )
    assert not result.is_relevant


def _run_all():
    tests = [obj for name, obj in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  ok  {test.__name__}")
    print(f"{len(tests)} filter tests passed")


if __name__ == "__main__":
    _run_all()
