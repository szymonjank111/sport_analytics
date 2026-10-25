import argparse
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from google.cloud import bigquery

from sport_analytics.ingestion.errors import NothingToLoadError, SourceError
from sport_analytics.ingestion.extract import extract_football_data
from sport_analytics.ingestion.http import build_session
from sport_analytics.ingestion.loader import (
    FOOTBALL_DATA_MATCHES,
    BigQueryWarehouse,
    Warehouse,
    build_rows,
)
from sport_analytics.ingestion.rate_limit import RateLimiter
from sport_analytics.ingestion.sources.football_data import MIN_INTERVAL, FootballDataClient
from sport_analytics.ingestion.storage import GcsStorage, Storage
from sport_analytics.settings import get_ingestion_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Deps:
    storage: Storage
    football_data: FootballDataClient
    warehouse: Warehouse


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_ingestion_settings()
    # Building a client makes no request yet, so a command may build the ones it does not use.
    with build_session() as session:
        deps = Deps(
            storage=GcsStorage(settings.gcp_project_id, settings.gcs_raw_bucket),
            football_data=FootballDataClient(
                settings.football_data_api_key.get_secret_value(),
                session,
                RateLimiter(MIN_INTERVAL),
            ),
            warehouse=BigQueryWarehouse(
                bigquery.Client(project=settings.gcp_project_id, location=settings.gcp_location),
                settings.bq_raw_dataset,
            ),
        )
        run(args, deps)


def run(args: argparse.Namespace, deps: Deps) -> None:
    """Runs the command; when the data is at fault, not the program, it exits with status 1."""
    try:
        match args.command, args.source:
            case "extract", "football-data":
                extract_football_data(
                    deps.football_data, deps.storage, args.competition, args.season, args.run_date
                )
            case "load", "football-data":
                loaded_at = datetime.now(UTC)
                rows = build_rows(deps.storage, FOOTBALL_DATA_MATCHES, args.run_date, loaded_at)
                deps.warehouse.load_partition(FOOTBALL_DATA_MATCHES, args.run_date, rows)
            case command:
                raise AssertionError(f"unhandled command {command}")
    except (SourceError, NothingToLoadError) as error:
        # A traceback would point at the code, which works as it should.
        context = " ".join(f"{name}={value}" for name, value in vars(args).items())
        logger.error("failed %s error=%s", context, error)
        raise SystemExit(1) from None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return _parser().parse_args(argv)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest", description="Move source data into raw.")
    commands = parser.add_subparsers(dest="command", required=True)

    extract = commands.add_parser("extract", help="Fetch from a source and store it in GCS.")
    sources = extract.add_subparsers(dest="source", required=True)
    football_data = sources.add_parser("football-data", help="Matches of a competition season.")
    football_data.add_argument("--competition", required=True, help="native code, such as PL")
    football_data.add_argument(
        "--season", type=int, required=True, help="start year, such as 2026 for 2026/27"
    )
    _add_run_date(football_data)

    load = commands.add_parser("load", help="Load the files of a run from GCS into BigQuery.")
    sources = load.add_subparsers(dest="source", required=True)
    _add_run_date(sources.add_parser("football-data", help="Matches."))
    return parser


def _add_run_date(parser: argparse.ArgumentParser) -> None:
    # Required, never today: a rerun of a past day must write to the same place.
    parser.add_argument(
        "--run-date", type=date.fromisoformat, required=True, help="such as 2026-10-25"
    )
