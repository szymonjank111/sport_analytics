from datetime import date

from sport_analytics.ingestion.paths import RawObject, run_prefix

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
