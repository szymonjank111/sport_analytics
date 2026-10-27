from datetime import date

import pytest

from fakes import (
    E0_SEASON,
    EPL_SEASON,
    MATCH_ROSTERS,
    PL_MATCHES,
    POL_SEASONS,
    FakeAdapter,
    InMemoryStorage,
    football_data_client,
    football_data_co_uk_client,
    understat_client,
)
from sport_analytics.ingestion.errors import SourceError
from sport_analytics.ingestion.extract import (
    extract_football_data,
    extract_football_data_co_uk,
    extract_understat,
)
from sport_analytics.ingestion.paths import RawObject, parse_raw_path

RUN_DATE = date(2026, 10, 25)
PATH = "raw/source=football_data/run_date=2026-10-25/competition=PL/season=2026/matches.json"


def test_stores_the_answer_unchanged() -> None:
    client = football_data_client(FakeAdapter((200, PL_MATCHES)))
    storage = InMemoryStorage()

    raw = extract_football_data(client, storage, "PL", 2026, RUN_DATE)

    assert raw.path == PATH
    assert storage.objects == {PATH: (PL_MATCHES, "application/json")}


def test_stores_nothing_from_a_bad_answer() -> None:
    client = football_data_client(FakeAdapter((200, b"{}")))
    storage = InMemoryStorage()

    with pytest.raises(SourceError):
        extract_football_data(client, storage, "PL", 2026, RUN_DATE)

    assert storage.objects == {}


def test_a_rerun_of_the_day_replaces_its_file() -> None:
    client = football_data_client(FakeAdapter((200, b'{"matches": []}'), (200, PL_MATCHES)))
    storage = InMemoryStorage()

    extract_football_data(client, storage, "PL", 2026, RUN_DATE)
    extract_football_data(client, storage, "PL", 2026, RUN_DATE)

    assert storage.objects == {PATH: (PL_MATCHES, "application/json")}


def test_fetches_the_seasons_of_divisions_and_extra_leagues_into_private_files() -> None:
    adapter = FakeAdapter((200, E0_SEASON), (200, E0_SEASON), (200, POL_SEASONS))
    storage = InMemoryStorage()

    extract_football_data_co_uk(
        football_data_co_uk_client(adapter), storage, ["E0", "POL"], [2025, 2026], RUN_DATE
    )

    assert sorted(storage.objects) == [
        "raw_private/source=football_data_co_uk/run_date=2026-10-25/competition=E0/season=2025/matches.csv",
        "raw_private/source=football_data_co_uk/run_date=2026-10-25/competition=E0/season=2026/matches.csv",
        "raw_private/source=football_data_co_uk/run_date=2026-10-25/competition=POL/matches.csv",
    ]


def test_fetches_a_finished_season_only_once() -> None:
    storage = InMemoryStorage()
    for season in (2025, 2026):
        earlier = RawObject("football_data_co_uk", date(2026, 9, 1), "E0", season, "matches", "csv")
        storage.write(earlier.path, E0_SEASON, "text/csv")
    adapter = FakeAdapter((200, E0_SEASON))

    extracted = extract_football_data_co_uk(
        football_data_co_uk_client(adapter), storage, ["E0"], [2025, 2026], RUN_DATE
    )

    assert [(raw.season, raw.run_date) for raw in extracted] == [(2026, RUN_DATE)]
    assert len(adapter.requests) == 1


def test_stores_nothing_from_a_file_that_breaks_the_contract() -> None:
    adapter = FakeAdapter((200, b"<html>Maintenance</html>"))
    storage = InMemoryStorage()

    with pytest.raises(SourceError):
        extract_football_data_co_uk(
            football_data_co_uk_client(adapter), storage, ["E0"], [2026], RUN_DATE
        )

    assert storage.objects == {}


def test_fetches_a_league_season_and_the_rosters_of_the_matches_played() -> None:
    adapter = FakeAdapter((200, EPL_SEASON), (200, MATCH_ROSTERS), (200, MATCH_ROSTERS))
    storage = InMemoryStorage()

    extract_understat(understat_client(adapter), storage, ["EPL"], [2026], RUN_DATE)

    prefix = "raw_private/source=understat/run_date=2026-10-25/competition=EPL/season=2026"
    assert sorted(storage.objects) == [
        f"{prefix}/league_matches.json",
        f"{prefix}/match=90001/match_players.json",
        f"{prefix}/match=90002/match_players.json",
    ]
    assert storage.objects[f"{prefix}/match=90001/match_players.json"][0] == MATCH_ROSTERS


def test_fetches_the_rosters_of_a_match_only_once() -> None:
    storage = InMemoryStorage()
    earlier = RawObject("understat", date(2026, 10, 1), "EPL", 2026, "match_players", "json", 90001)
    storage.write(earlier.path, MATCH_ROSTERS, "application/json")
    adapter = FakeAdapter((200, EPL_SEASON), (200, MATCH_ROSTERS))

    extracted = extract_understat(understat_client(adapter), storage, ["EPL"], [2026], RUN_DATE)

    assert [(raw.entity, raw.match_id) for raw in extracted] == [
        ("league_matches", None),
        ("match_players", 90002),
    ]


def test_a_finished_season_comes_from_storage_with_the_rosters_still_to_fetch() -> None:
    storage = InMemoryStorage()
    season = RawObject("understat", date(2026, 5, 1), "EPL", 2025, "league_matches", "json")
    storage.write(season.path, EPL_SEASON, "application/json")
    rosters = RawObject("understat", date(2026, 5, 1), "EPL", 2025, "match_players", "json", 90001)
    storage.write(rosters.path, MATCH_ROSTERS, "application/json")
    adapter = FakeAdapter((200, MATCH_ROSTERS))

    extracted = extract_understat(understat_client(adapter), storage, ["EPL"], [2025], RUN_DATE)

    assert [(raw.season, raw.match_id) for raw in extracted] == [(2025, 90002)]
    assert [request.url for request in adapter.requests] == [
        "https://understat.com/getMatchData/90002"
    ]


def test_keeps_the_rosters_fetched_before_a_failure() -> None:
    adapter = FakeAdapter((200, EPL_SEASON), (200, MATCH_ROSTERS), (200, b"{}"))
    storage = InMemoryStorage()

    with pytest.raises(SourceError, match="match_players contract"):
        extract_understat(understat_client(adapter), storage, ["EPL"], [2026], RUN_DATE)

    assert [(raw.entity, raw.match_id) for raw in map(parse_raw_path, storage.objects)] == [
        ("league_matches", None),
        ("match_players", 90001),
    ]
