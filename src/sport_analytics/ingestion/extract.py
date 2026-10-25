import logging
from datetime import date

from sport_analytics.ingestion.paths import RawObject
from sport_analytics.ingestion.sources.football_data import FootballDataClient, parse_matches
from sport_analytics.ingestion.storage import Storage

logger = logging.getLogger(__name__)


def extract_football_data(
    client: FootballDataClient, storage: Storage, competition: str, season: int, run_date: date
) -> RawObject:
    body = client.fetch_matches(competition, season)
    # Checked before it is written, so a bad answer never reaches the raw layer.
    matches = parse_matches(body)
    raw = RawObject("football_data", run_date, competition, season, "matches", "json")
    storage.write(raw.path, body, "application/json")
    logger.info(
        "extracted source=%s competition=%s season=%d matches=%d uri=%s",
        raw.source,
        competition,
        season,
        len(matches),
        storage.uri(raw.path),
    )
    return raw
