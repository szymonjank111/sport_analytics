import argparse
import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime

from google.cloud import bigquery

from sport_analytics.ingestion.extract import extract_football_data
from sport_analytics.ingestion.http import build_session
from sport_analytics.ingestion.loader import FOOTBALL_DATA_MATCHES, build_rows, load_partition
from sport_analytics.ingestion.rate_limit import RateLimiter
from sport_analytics.ingestion.sources.football_data import MIN_INTERVAL, FootballDataClient
from sport_analytics.ingestion.storage import GcsStorage
from sport_analytics.settings import get_ingestion_settings


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_ingestion_settings()
    raw = GcsStorage(settings.gcp_project_id, settings.gcs_raw_bucket)
    match args.command, args.source:
        case "extract", "football-data":
            with build_session() as session:
                client = FootballDataClient(
                    settings.football_data_api_key.get_secret_value(),
                    session,
                    RateLimiter(MIN_INTERVAL),
                )
                extract_football_data(client, raw, args.competition, args.season, args.run_date)
        case "load", "football-data":
            rows = build_rows(raw, FOOTBALL_DATA_MATCHES, args.run_date, datetime.now(UTC))
            warehouse = bigquery.Client(
                project=settings.gcp_project_id, location=settings.gcp_location
            )
            load_partition(
                warehouse, settings.bq_raw_dataset, FOOTBALL_DATA_MATCHES, args.run_date, rows
            )
        case command:
            raise AssertionError(f"unhandled command {command}")


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
