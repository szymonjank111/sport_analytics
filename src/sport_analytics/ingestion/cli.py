import argparse
import logging
from collections.abc import Sequence
from datetime import date

import requests

from sport_analytics.ingestion.extract import extract_football_data
from sport_analytics.ingestion.sources.football_data import FootballDataClient
from sport_analytics.ingestion.storage import GcsStorage
from sport_analytics.settings import get_ingestion_settings


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_ingestion_settings()
    raw = GcsStorage(settings.gcp_project_id, settings.gcs_raw_bucket)
    match args.command, args.source:
        case "extract", "football-data":
            with requests.Session() as session:
                client = FootballDataClient(
                    settings.football_data_api_key.get_secret_value(), session
                )
                extract_football_data(client, raw, args.competition, args.season, args.run_date)
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
    # Required, never today: a rerun of a past day must write to the same place.
    football_data.add_argument(
        "--run-date", type=date.fromisoformat, required=True, help="such as 2026-10-25"
    )
    return parser
