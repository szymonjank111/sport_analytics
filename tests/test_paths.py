from datetime import date

import pytest

from sport_analytics.ingestion.paths import RawObject, parse_raw_path, run_prefix

RUN_DATE = date(2026, 10, 25)


def test_path_of_a_season_file() -> None:
    raw = RawObject("football_data", RUN_DATE, "PL", 2026, "matches", "json")

    assert raw.path == (
        "raw/source=football_data/run_date=2026-10-25/competition=PL/season=2026/matches.json"
    )


def test_path_of_a_file_spanning_seasons_has_no_season() -> None:
    raw = RawObject("football_data_co_uk", RUN_DATE, "POL", None, "matches", "csv")

    assert raw.path == (
        "raw/source=football_data_co_uk/run_date=2026-10-25/competition=POL/matches.csv"
    )


def test_files_of_a_run_share_its_prefix() -> None:
    raw = RawObject("football_data", RUN_DATE, "PL", 2026, "matches", "json")

    assert raw.path.startswith(run_prefix("football_data", RUN_DATE))


@pytest.mark.parametrize("season", [2026, None])
def test_a_path_parses_back_into_its_object(season: int | None) -> None:
    raw = RawObject("football_data", RUN_DATE, "PL", season, "matches", "json")

    assert parse_raw_path(raw.path) == raw


@pytest.mark.parametrize(
    "path",
    [
        "raw/source=football_data/run_date=2026-10-25/notes.txt",
        "raw/source=football_data/run_date=2026-10-25/competition=PL/season=26/matches.json",
        "other/source=football_data/run_date=2026-10-25/competition=PL/matches.json",
    ],
)
def test_refuses_a_path_outside_the_layout(path: str) -> None:
    with pytest.raises(ValueError, match="not a raw path"):
        parse_raw_path(path)
