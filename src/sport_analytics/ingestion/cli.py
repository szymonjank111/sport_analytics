import argparse
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from google.cloud import bigquery

from sport_analytics.ingestion.errors import NothingToLoadError, SourceError
from sport_analytics.ingestion.extract import (
    extract_football_data,
    extract_football_data_co_uk,
    extract_understat,
)
from sport_analytics.ingestion.http import build_session
from sport_analytics.ingestion.loader import (
    FOOTBALL_DATA_CO_UK_MATCHES,
    FOOTBALL_DATA_MATCHES,
    UNDERSTAT_LEAGUE_MATCHES,
    UNDERSTAT_MATCH_PLAYERS,
    BigQueryWarehouse,
    RawEntity,
    Warehouse,
    build_rows,
)
from sport_analytics.ingestion.rate_limit import RateLimiter
from sport_analytics.ingestion.seasons import current_season
from sport_analytics.ingestion.sources.football_data import (
    CALENDAR_YEAR,
    COMPETITIONS,
    MIN_INTERVAL,
    FootballDataClient,
)
from sport_analytics.ingestion.sources.football_data_co_uk import (
    DIVISIONS,
    EXTRA_LEAGUES,
    FootballDataCoUkClient,
)
from sport_analytics.ingestion.sources.football_data_co_uk import (
    MIN_INTERVAL as CO_UK_MIN_INTERVAL,
)
from sport_analytics.ingestion.sources.understat import LEAGUES, UnderstatClient
from sport_analytics.ingestion.sources.understat import MIN_INTERVAL as UNDERSTAT_MIN_INTERVAL
from sport_analytics.ingestion.storage import GcsStorage, Storage
from sport_analytics.settings import get_ingestion_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Deps:
    storage: Storage
    football_data: FootballDataClient
    football_data_co_uk: FootballDataCoUkClient
    understat: UnderstatClient
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
            football_data_co_uk=FootballDataCoUkClient(session, RateLimiter(CO_UK_MIN_INTERVAL)),
            understat=UnderstatClient(session, RateLimiter(UNDERSTAT_MIN_INTERVAL)),
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
                for competition in args.competition or COMPETITIONS:
                    season = args.season or current_season(
                        args.run_date, competition in CALENDAR_YEAR
                    )
                    extract_football_data(
                        deps.football_data, deps.storage, competition, season, args.run_date
                    )
            case "extract", "football-data-co-uk":
                extract_football_data_co_uk(
                    deps.football_data_co_uk,
                    deps.storage,
                    args.competition or (*DIVISIONS, *EXTRA_LEAGUES),
                    _seasons(args),
                    args.run_date,
                )
            case "extract", "understat":
                extract_understat(
                    deps.understat,
                    deps.storage,
                    args.competition or LEAGUES,
                    _seasons(args),
                    args.run_date,
                )
            case "load", "football-data":
                _load(deps, FOOTBALL_DATA_MATCHES, args.run_date)
            case "load", "football-data-co-uk":
                _load(deps, FOOTBALL_DATA_CO_UK_MATCHES, args.run_date)
            case "load", "understat":
                _load(deps, UNDERSTAT_LEAGUE_MATCHES, args.run_date)
                try:
                    _load(deps, UNDERSTAT_MATCH_PLAYERS, args.run_date)
                except NothingToLoadError:
                    # Rosters are fetched once, after the match, so a run may have none.
                    logger.info(
                        "skipped table=%s run_date=%s reason=no_new_matches",
                        UNDERSTAT_MATCH_PLAYERS.table,
                        args.run_date,
                    )
            case command:
                raise AssertionError(f"unhandled command {command}")
    except (SourceError, NothingToLoadError) as error:
        # A traceback would point at the code, which works as it should.
        context = " ".join(f"{name}={value}" for name, value in vars(args).items())
        logger.error("failed %s error=%s", context, error)
        raise SystemExit(1) from None


def _seasons(args: argparse.Namespace) -> list[int]:
    current = current_season(args.run_date)
    history = range(args.history_from, current + 1) if args.history_from else ()
    return sorted({*(args.season or ()), *history}) or [current]


def _load(deps: Deps, entity: RawEntity, run_date: date) -> None:
    rows = build_rows(deps.storage, entity, run_date, datetime.now(UTC))
    deps.warehouse.load_partition(entity, run_date, rows)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return _parser().parse_args(argv)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest", description="Move source data into raw.")
    commands = parser.add_subparsers(dest="command", required=True)

    extract = commands.add_parser("extract", help="Fetch from a source and store it in GCS.")
    sources = extract.add_subparsers(dest="source", required=True)
    football_data = sources.add_parser("football-data", help="Matches of competition seasons.")
    # One run fetches every competition, since the rate limiter only spaces the requests of one
    # process.
    football_data.add_argument(
        "--competition",
        action="append",
        choices=COMPETITIONS,
        help="native code, such as PL; repeat it for more; all of them by default",
    )
    football_data.add_argument(
        "--season",
        type=int,
        help="start year, such as 2026 for 2026/27; the current one by default",
    )
    _add_run_date(football_data)

    co_uk = sources.add_parser(
        "football-data-co-uk", help="Matches of division seasons and of extra leagues."
    )
    co_uk.add_argument(
        "--competition",
        action="append",
        choices=(*DIVISIONS, *EXTRA_LEAGUES),
        help="division such as E0, or extra league such as POL, whose file has every season;"
        " repeat it for more; all of them by default",
    )
    co_uk.add_argument(
        "--season",
        type=int,
        action="append",
        help="start year of a division season; repeat it for more; the current one by default",
    )
    co_uk.add_argument(
        "--history-from", type=int, help="start year of the first season to fetch, up to now"
    )
    _add_run_date(co_uk)

    understat = sources.add_parser(
        "understat", help="Matches of league seasons with xG, and the rosters of those played."
    )
    understat.add_argument(
        "--competition",
        action="append",
        choices=LEAGUES,
        help="league code, such as EPL; repeat it for more; all of them by default",
    )
    understat.add_argument(
        "--season",
        type=int,
        action="append",
        help="start year, such as 2026 for 2026/27; repeat it for more; the current one by default",
    )
    understat.add_argument(
        "--history-from", type=int, help="start year of the first season to fetch, up to now"
    )
    _add_run_date(understat)

    load = commands.add_parser("load", help="Load the files of a run from GCS into BigQuery.")
    sources = load.add_subparsers(dest="source", required=True)
    _add_run_date(sources.add_parser("football-data", help="Matches."))
    _add_run_date(sources.add_parser("football-data-co-uk", help="Matches."))
    _add_run_date(
        sources.add_parser("understat", help="Matches, and the rosters of the matches played.")
    )
    return parser


def _add_run_date(parser: argparse.ArgumentParser) -> None:
    # Required, never today: a rerun of a past day must write to the same place.
    parser.add_argument(
        "--run-date", type=date.fromisoformat, required=True, help="such as 2026-10-25"
    )
