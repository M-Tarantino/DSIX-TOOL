import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.retry import with_backoff  # noqa: E402


class _RateLimitError(Exception):
    status_code = 429


class _AuthError(Exception):
    pass


def test_retries_and_succeeds_on_transient_error():
    calls = {"n": 0}

    @with_backoff(max_retries=3, base_delay=0.01)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _RateLimitError("429 rate limit exceeded")
        return "ok"

    with patch("src.retry.time.sleep"):  # skip real waiting in tests
        assert flaky() == "ok"
    assert calls["n"] == 3


def test_gives_up_after_max_retries():
    calls = {"n": 0}

    @with_backoff(max_retries=2, base_delay=0.01)
    def always_flaky():
        calls["n"] += 1
        raise _RateLimitError("429 rate limit exceeded")

    with patch("src.retry.time.sleep"):
        try:
            always_flaky()
            assert False, "expected the error to propagate after exhausting retries"
        except _RateLimitError:
            pass
    assert calls["n"] == 3  # initial attempt + 2 retries


def test_non_transient_error_raises_immediately():
    calls = {"n": 0}

    @with_backoff(max_retries=5, base_delay=0.01)
    def bad_auth():
        calls["n"] += 1
        raise _AuthError("401 invalid api key")

    with patch("src.retry.time.sleep") as sleep_mock:
        try:
            bad_auth()
            assert False, "expected immediate raise on non-transient error"
        except _AuthError:
            pass
    assert calls["n"] == 1  # no retries attempted
    sleep_mock.assert_not_called()


def _run_all():
    tests = [obj for name, obj in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  ok  {test.__name__}")
    print(f"{len(tests)} retry tests passed")


if __name__ == "__main__":
    _run_all()
