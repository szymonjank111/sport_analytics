import json
from datetime import UTC, date, datetime

import pytest

from fakes import MATCH_ROSTERS, PL_MATCHES, InMemoryStorage
from sport_analytics.ingestion.errors import NothingToLoadError
from sport_analytics.ingestion.loader import (
    FOOTBALL_DATA_MATCHES,
    UNDERSTAT_MATCH_PLAYERS,
    build_rows,
)
from sport_analytics.ingestion.paths import RawObject

RUN_DATE = date(2026, 10, 25)
LOADED_AT = datetime(2026, 10, 25, 6, 30, tzinfo=UTC)


def stored(*objects: RawObject, body: bytes = PL_MATCHES) -> InMemoryStorage:
    storage = InMemoryStorage()
    for raw in objects:
        storage.write(raw.path, body, "application/json")
    return storage


def matches(run_date: date, competition: str = "PL", entity: str = "matches") -> RawObject:
    return RawObject("football_data", run_date, competition, 2026, entity, "json")


def test_a_row_for_each_match_of_the_run() -> None:
    raw = matches(RUN_DATE)

    rows = build_rows(stored(raw), FOOTBALL_DATA_MATCHES, RUN_DATE, LOADED_AT)

    assert [row["payload"] for row in rows] == json.loads(PL_MATCHES)["matches"]
    assert rows[0] | {"payload": None} == {
        "_run_date": "2026-10-25",
        "_competition": "PL",
        "_season": 2026,
        "_gcs_uri": f"memory://{raw.path}",
        "_loaded_at": "2026-10-25T06:30:00+00:00",
        "payload": None,
    }


def test_a_row_for_each_player_of_a_match_whose_uri_names_the_match() -> None:
    raw = RawObject("understat", RUN_DATE, "EPL", 2026, "match_players", "json", 90001)

    rows = build_rows(stored(raw, body=MATCH_ROSTERS), UNDERSTAT_MATCH_PLAYERS, RUN_DATE, LOADED_AT)

    assert [row["payload"]["player_id"] for row in rows] == ["5001", "5002", "5003", "6001", "6002"]
    assert {row["_gcs_uri"] for row in rows} == {f"memory://{raw.path}"}
    assert "/match=90001/" in raw.path


def test_takes_only_files_of_the_entity_from_the_run() -> None:
    storage = stored(
        matches(RUN_DATE),
        matches(RUN_DATE, competition="PD"),
        matches(date(2026, 10, 24)),
        matches(RUN_DATE, entity="standings"),
    )

    rows = build_rows(storage, FOOTBALL_DATA_MATCHES, RUN_DATE, LOADED_AT)

    assert sorted({row["_competition"] for row in rows}) == ["PD", "PL"]
    assert len(rows) == 6


def test_a_run_without_files_has_nothing_to_load() -> None:
    storage = stored(matches(date(2026, 10, 24)))

    with pytest.raises(NothingToLoadError, match="run_date=2026-10-25"):
        build_rows(storage, FOOTBALL_DATA_MATCHES, RUN_DATE, LOADED_AT)


def test_loads_a_stored_file_without_checking_it_again() -> None:
    storage = stored(matches(RUN_DATE), body=b'{"matches": [{"id": 1, "status": "NEW"}]}')

    rows = build_rows(storage, FOOTBALL_DATA_MATCHES, RUN_DATE, LOADED_AT)

    assert [row["payload"] for row in rows] == [{"id": 1, "status": "NEW"}]
