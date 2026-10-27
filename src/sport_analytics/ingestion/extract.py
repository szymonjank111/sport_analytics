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
from sport_analytics.ingestion.sources.understat import (
    UnderstatClient,
    parse_league,
    parse_match_players,
    split_league_matches,
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


def extract_understat(
    client: UnderstatClient,
    storage: Storage,
    leagues: Iterable[str],
    seasons: Iterable[int],
    run_date: date,
) -> list[RawObject]:
    """Fetches the matches of league seasons and the rosters of each match played.

    A finished season and the rosters of a played match no longer change, so they are fetched
    only if no run has stored them yet.
    """
    source = "understat"
    stored = [parse_raw_path(path) for path in storage.list_paths(source_prefix(source))]
    stored_seasons = {
        (raw.competition, raw.season): raw.path for raw in stored if raw.entity == "league_matches"
    }
    stored_matches = {raw.match_id for raw in stored if raw.entity == "match_players"}
    current = current_season(run_date)
    extracted: list[RawObject] = []
    for league in leagues:
        for season in seasons:
            stored_season = stored_seasons.get((league, season))
            if season < current and stored_season is not None:
                logger.info(
                    "skipped source=%s competition=%s season=%d reason=stored",
                    source,
                    league,
                    season,
                )
                # Still read, since a run that failed may have left rosters of it to fetch.
                matches = split_league_matches(storage.read(stored_season))
            else:
                body = client.fetch_league(league, season)
                matches = parse_league(body)
                raw = RawObject(source, run_date, league, season, "league_matches", "json")
                _store(storage, raw, body, "application/json", len(matches))
                extracted.append(raw)
            for match in matches:
                match_id = int(match["id"])
                if not match["isResult"] or match_id in stored_matches:
                    continue
                body = client.fetch_match(match_id)
                players = parse_match_players(body)
                raw = RawObject(source, run_date, league, season, "match_players", "json", match_id)
                _store(storage, raw, body, "application/json", len(players))
                extracted.append(raw)
    return extracted


def _store(storage: Storage, raw: RawObject, body: bytes, content_type: str, records: int) -> None:
    storage.write(raw.path, body, content_type)
    logger.info(
        "extracted source=%s competition=%s season=%s records=%d uri=%s",
        raw.source,
        raw.competition,
        raw.season,
        records,
        storage.uri(raw.path),
    )
