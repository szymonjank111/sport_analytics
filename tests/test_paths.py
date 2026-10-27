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
    raw = RawObject("football_data", RUN_DATE, "PL", None, "matches", "json")

    assert raw.path == "raw/source=football_data/run_date=2026-10-25/competition=PL/matches.json"


def test_files_of_a_private_source_stay_apart() -> None:
    raw = RawObject("football_data_co_uk", RUN_DATE, "POL", None, "matches", "csv")

    assert raw.path == (
        "raw_private/source=football_data_co_uk/run_date=2026-10-25/competition=POL/matches.csv"
    )


def test_a_file_of_a_single_match_has_its_own_folder() -> None:
    raw = RawObject("understat", RUN_DATE, "EPL", 2026, "match_players", "json", 90001)

    assert raw.path == (
        "raw_private/source=understat/run_date=2026-10-25/competition=EPL/season=2026"
        "/match=90001/match_players.json"
    )


def test_files_of_a_run_share_its_prefix() -> None:
    raw = RawObject("football_data", RUN_DATE, "PL", 2026, "matches", "json")

    assert raw.path.startswith(run_prefix("football_data", RUN_DATE))


@pytest.mark.parametrize(
    "raw",
    [
        RawObject("football_data", RUN_DATE, "PL", 2026, "matches", "json"),
        RawObject("football_data_co_uk", RUN_DATE, "E0", 2026, "matches", "csv"),
        RawObject("football_data_co_uk", RUN_DATE, "POL", None, "matches", "csv"),
        RawObject("understat", RUN_DATE, "EPL", 2026, "match_players", "json", 90001),
    ],
)
def test_a_path_parses_back_into_its_object(raw: RawObject) -> None:
    assert parse_raw_path(raw.path) == raw


@pytest.mark.parametrize(
    "path",
    [
        "raw/source=football_data/run_date=2026-10-25/notes.txt",
        "raw/source=football_data/run_date=2026-10-25/competition=PL/season=26/matches.json",
        "other/source=football_data/run_date=2026-10-25/competition=PL/matches.json",
        "raw/source=football_data_co_uk/run_date=2026-10-25/competition=POL/matches.csv",
        "raw_private/source=football_data/run_date=2026-10-25/competition=PL/matches.json",
        "raw_private/source=understat/run_date=2026-10-25/competition=EPL/match=x/players.json",
    ],
)
def test_refuses_a_path_outside_the_layout(path: str) -> None:
    with pytest.raises(ValueError, match="not a raw path"):
        parse_raw_path(path)
