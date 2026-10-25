import pytest

from fakes import FakeClock
from sport_analytics.ingestion.rate_limit import RateLimiter


def limiter(clock: FakeClock) -> RateLimiter:
    return RateLimiter(6.5, clock=clock, sleep=clock.sleep)


def test_the_first_request_goes_at_once() -> None:
    clock = FakeClock()

    limiter(clock).wait()

    assert clock.sleeps == []


def test_waits_for_the_rest_of_the_interval() -> None:
    clock = FakeClock()
    rate = limiter(clock)

    rate.wait()
    clock.now += 2
    rate.wait()

    assert clock.sleeps == [pytest.approx(4.5)]


def test_does_not_wait_once_the_interval_passed() -> None:
    clock = FakeClock()
    rate = limiter(clock)

    rate.wait()
    clock.now += 7
    rate.wait()

    assert clock.sleeps == []


def test_spaces_every_request_from_the_one_before() -> None:
    clock = FakeClock()
    rate = limiter(clock)

    for _ in range(3):
        rate.wait()

    assert clock.sleeps == [pytest.approx(6.5)] * 2
