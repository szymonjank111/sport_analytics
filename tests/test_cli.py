import shlex

import pytest

from fakes import PL_MATCHES, FakeAdapter, FakeWarehouse, InMemoryStorage, football_data_client
from sport_analytics.ingestion.cli import Deps, parse_args, run

EXTRACT = parse_args(
    shlex.split("extract football-data --competition PL --season 2026 --run-date 2026-10-25")
)
LOAD = parse_args(shlex.split("load football-data --run-date 2026-10-25"))


def deps(storage: InMemoryStorage, warehouse: FakeWarehouse, *responses: tuple[int, bytes]) -> Deps:
    return Deps(storage, football_data_client(FakeAdapter(*responses)), warehouse)


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
        "failed command=extract source=football-data competition=PL season=2026"
        " run_date=2026-10-25 error=football-data.org answered 403:"
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
