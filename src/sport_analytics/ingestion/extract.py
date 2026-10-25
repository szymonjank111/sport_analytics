import logging
from collections.abc import Iterable
from datetime import date

from sport_analytics.ingestion.paths import RawObject, parse_raw_path, source_prefix
from sport_analytics.ingestion.seasons import current_season
from sport_analytics.ingestion.sources.football_data import FootballDataClient, parse_matches
from sport_analytics.ingestion.sources.football_data_co_uk import (
    EXTRA_LEAGUES,
    FootballDataCoUkClient,
    parse_division_season,
    parse_extra_league,
)
from sport_analytics.ingestion.storage import Storage

logger = logging.getLogger(__name__)


def extract_football_data(
    client: FootballDataClient, storage: Storage, competition: str, season: int, run_date: date
) -> RawObject:
    body = client.fetch_matches(competition, season)
    # Checked before it is written, so a bad answer never reaches the raw layer.
    matches = parse_matches(body)
    raw = RawObject("football_data", run_date, competition, season, "matches", "json")
    _store(storage, raw, body, "application/json", len(matches))
    return raw


def extract_football_data_co_uk(
    client: FootballDataCoUkClient,
    storage: Storage,
    competitions: Iterable[str],
    seasons: Iterable[int],
    run_date: date,
) -> list[RawObject]:
    """Fetches the seasons of the divisions and the whole file of each extra league.

    A finished season no longer changes, so it is fetched only if no run has stored it yet.
    """
    source = "football_data_co_uk"
    stored = {
        (raw.competition, raw.season)
        for raw in map(parse_raw_path, storage.list_paths(source_prefix(source)))
    }
    current = current_season(run_date)
    extracted: list[RawObject] = []
    for competition in competitions:
        if competition in EXTRA_LEAGUES:
            body = client.fetch_extra_league(competition)
            matches = parse_extra_league(body)
            raw = RawObject(source, run_date, competition, None, "matches", "csv")
            _store(storage, raw, body, "text/csv", len(matches))
            extracted.append(raw)
            continue
        for season in seasons:
            if season < current and (competition, season) in stored:
                logger.info(
                    "skipped source=%s competition=%s season=%d reason=stored",
                    source,
                    competition,
                    season,
                )
                continue
            body = client.fetch_season(competition, season)
            matches = parse_division_season(body)
            raw = RawObject(source, run_date, competition, season, "matches", "csv")
            _store(storage, raw, body, "text/csv", len(matches))
            extracted.append(raw)
    return extracted


def _store(storage: Storage, raw: RawObject, body: bytes, content_type: str, matches: int) -> None:
    storage.write(raw.path, body, content_type)
    logger.info(
        "extracted source=%s competition=%s season=%s matches=%d uri=%s",
        raw.source,
        raw.competition,
        raw.season,
        matches,
        storage.uri(raw.path),
    )
