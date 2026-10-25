from datetime import date

import pytest

from fakes import PL_MATCHES, FakeAdapter, InMemoryStorage, football_data_client
from sport_analytics.ingestion.errors import SourceError
from sport_analytics.ingestion.extract import extract_football_data

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
