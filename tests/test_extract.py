from datetime import date

import pytest

from fakes import (
    E0_SEASON,
    PL_MATCHES,
    POL_SEASONS,
    FakeAdapter,
    InMemoryStorage,
    football_data_client,
    football_data_co_uk_client,
)
from sport_analytics.ingestion.errors import SourceError
from sport_analytics.ingestion.extract import extract_football_data, extract_football_data_co_uk
from sport_analytics.ingestion.paths import RawObject

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
