from datetime import date

import pytest

from sport_analytics.ingestion.seasons import current_season


@pytest.mark.parametrize(
    ("run_date", "season"),
    [(date(2027, 6, 30), 2026), (date(2027, 7, 1), 2027), (date(2026, 10, 25), 2026)],
)
def test_a_split_season_starts_in_july(run_date: date, season: int) -> None:
    assert current_season(run_date) == season


def test_a_calendar_season_is_the_year() -> None:
    assert current_season(date(2027, 3, 1), calendar_year=True) == 2027
