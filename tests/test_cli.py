import logging
import shlex
from datetime import date

import pytest

from fakes import (
    CL_MATCHES,
    E0_SEASON,
    EPL_SEASON,
    MATCH_ROSTERS,
    PL_MATCHES,
    POL_SEASONS,
    FakeAdapter,
    FakeWarehouse,
    InMemoryStorage,
    football_data_client,
    football_data_co_uk_client,
    understat_client,
)
from sport_analytics.ingestion.cli import Deps, parse_args, run
from sport_analytics.ingestion.paths import RawObject, parse_raw_path
from sport_analytics.ingestion.sources.football_data import COMPETITIONS

EXTRACT = parse_args(
    shlex.split("extract football-data --competition PL --season 2026 --run-date 2026-10-25")
)
LOAD = parse_args(shlex.split("load football-data --run-date 2026-10-25"))


def deps(storage: InMemoryStorage, warehouse: FakeWarehouse, *responses: tuple[int, bytes]) -> Deps:
    adapter = FakeAdapter(*responses)
    return Deps(
        storage,
        football_data_client(adapter),
        football_data_co_uk_client(adapter),
        understat_client(adapter),
        warehouse,
    )


def stored_seasons(storage: InMemoryStorage) -> set[tuple[str, int | None]]:
    return {(raw.competition, raw.season) for raw in map(parse_raw_path, storage.objects)}


def test_extracts_the_current_season_of_every_competition() -> None:
    storage = InMemoryStorage()
    answers = [(200, PL_MATCHES)] * len(COMPETITIONS)

    run(
        parse_args(["extract", "football-data", "--run-date", "2027-03-01"]),
        deps(storage, FakeWarehouse(), *answers),
    )

    expected = {(competition, 2026) for competition in COMPETITIONS if competition != "BSA"}
    assert stored_seasons(storage) == expected | {("BSA", 2027)}


def test_extracts_the_given_competitions_and_season() -> None:
    storage = InMemoryStorage()
    command = "extract football-data --competition PL --competition CL --season 2025"

    run(
        parse_args([*shlex.split(command), "--run-date", "2026-10-25"]),
        deps(storage, FakeWarehouse(), (200, PL_MATCHES), (200, CL_MATCHES)),
    )

    assert stored_seasons(storage) == {("PL", 2025), ("CL", 2025)}


def test_extracts_and_loads_a_day() -> None:
    warehouse = FakeWarehouse()
    day = deps(InMemoryStorage(), warehouse, (200, PL_MATCHES))

    run(EXTRACT, day)
    run(LOAD, day)

    [rows] = warehouse.partitions.values()
    assert len(rows) == 3


def test_a_failing_source_exits_with_the_reason(caplog: pytest.LogCaptureFixture) -> None:
    answer = b'{"message": "Please check your subscription.", "errorCode": 403}'
    storage = InMemoryStorage()

    with pytest.raises(SystemExit) as exit_info:
        run(EXTRACT, deps(storage, FakeWarehouse(), (403, answer)))

    assert exit_info.value.code == 1
    assert caplog.messages == [
        "failed command=extract source=football-data competition=['PL'] season=2026"
        " run_date=2026-10-25 error=football-data.org answered 403 for PL 2026:"
        " Please check your subscription."
    ]
    assert storage.objects == {}


def test_a_day_without_files_exits_without_loading(caplog: pytest.LogCaptureFixture) -> None:
    warehouse = FakeWarehouse()

    with pytest.raises(SystemExit) as exit_info:
        run(LOAD, deps(InMemoryStorage(), warehouse))

    assert exit_info.value.code == 1
    assert "error=no matches files under raw/source=football_data/run_date=2026-10-25/" in (
        caplog.text
    )
    assert warehouse.partitions == {}


def test_a_fault_of_the_program_keeps_its_traceback() -> None:
    storage = InMemoryStorage()
    storage.write("raw/source=football_data/run_date=2026-10-25/notes.txt", b"", "text/plain")

    with pytest.raises(ValueError, match="not a raw path"):
        run(LOAD, deps(storage, FakeWarehouse()))


def test_the_run_date_is_required() -> None:
    with pytest.raises(SystemExit) as exit_info:
        parse_args(shlex.split("load football-data"))

    assert exit_info.value.code == 2


def test_extracts_the_history_of_a_division_and_loads_it_with_an_extra_league() -> None:
    storage, warehouse = InMemoryStorage(), FakeWarehouse()
    answers = [(200, E0_SEASON)] * 3 + [(200, POL_SEASONS)]
    day = deps(storage, warehouse, *answers)
    command = "football-data-co-uk --competition E0 --competition POL --history-from 2024"

    run(parse_args(["extract", *shlex.split(command), "--run-date", "2026-10-25"]), day)
    run(parse_args(["load", "football-data-co-uk", "--run-date", "2026-10-25"]), day)

    assert stored_seasons(storage) == {("E0", 2024), ("E0", 2025), ("E0", 2026), ("POL", None)}
    [rows] = warehouse.partitions.values()
    assert len(rows) == 3 * 3 + 3


def test_extracts_and_loads_league_seasons_with_the_rosters_of_the_matches_played() -> None:
    storage, warehouse = InMemoryStorage(), FakeWarehouse()
    answers = [(200, EPL_SEASON), (200, MATCH_ROSTERS), (200, MATCH_ROSTERS)] * 2
    day = deps(storage, warehouse, *answers)
    command = "understat --competition EPL --history-from 2025"

    run(parse_args(["extract", *shlex.split(command), "--run-date", "2026-10-25"]), day)
    run(parse_args(["load", "understat", "--run-date", "2026-10-25"]), day)

    assert stored_seasons(storage) == {("EPL", 2025), ("EPL", 2026)}
    assert {table: len(rows) for (table, _), rows in warehouse.partitions.items()} == {
        "understat__league_matches": 2 * 3,
        "understat__match_players": 2 * 2 * 5,
    }


def test_loads_a_day_without_new_rosters(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    storage, warehouse = InMemoryStorage(), FakeWarehouse()
    season = RawObject("understat", date(2026, 10, 25), "EPL", 2026, "league_matches", "json")
    storage.write(season.path, EPL_SEASON, "application/json")

    run(parse_args(shlex.split("load understat --run-date 2026-10-25")), deps(storage, warehouse))

    assert [table for table, _ in warehouse.partitions] == ["understat__league_matches"]
    assert caplog.messages[-1] == (
        "skipped table=understat__match_players run_date=2026-10-25 reason=no_new_matches"
    )
