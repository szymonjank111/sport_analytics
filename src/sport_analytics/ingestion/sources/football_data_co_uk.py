import csv
import io
from typing import Annotated, Any, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, ValidationError

from sport_analytics.ingestion.errors import SourceError, broken_contract
from sport_analytics.ingestion.http import NETWORK_ERRORS, TIMEOUT
from sport_analytics.ingestion.rate_limit import RateLimiter

BASE_URL = "https://football-data.co.uk"
MIN_INTERVAL = 3.0
"""Seconds between requests: the site sets no limit, so this is a polite pace."""
DIVISIONS = ("E0", "E1", "SP1", "D1", "I1", "F1", "N1", "P1")
"""Leagues with a file for each season, with match statistics."""
EXTRA_LEAGUES = ("POL", "BRA")
"""Leagues with one file for all seasons, with results and odds only."""

# 21/08/2026, or 21/08/17 in most divisions in 2017/18.
Day = Annotated[str, StringConstraints(pattern=r"^\d{2}/\d{2}/(\d{2}|\d{4})$")]
Team = Annotated[str, StringConstraints(min_length=1)]
# Empty for a match that was never played, such as Chapecoense's last one in 2016.
Goals = Annotated[str, StringConstraints(pattern=r"^\d*$")]
Result = Literal["H", "D", "A", ""]


class _Contract(BaseModel):
    """The columns the pipeline reads, all text; any other may come and go without breaking it."""

    model_config = ConfigDict(extra="ignore", frozen=True)


class DivisionMatch(_Contract):
    date: Day = Field(alias="Date")
    home_team: Team = Field(alias="HomeTeam")
    away_team: Team = Field(alias="AwayTeam")
    home_goals: Goals = Field(alias="FTHG")
    away_goals: Goals = Field(alias="FTAG")
    result: Result = Field(alias="FTR")


class ExtraLeagueMatch(_Contract):
    # 2026/2027, or 2026 for a season within a year.
    season: Annotated[str, StringConstraints(pattern=r"^\d{4}(/\d{4})?$")] = Field(alias="Season")
    date: Day = Field(alias="Date")
    home_team: Team = Field(alias="Home")
    away_team: Team = Field(alias="Away")
    home_goals: Goals = Field(alias="HG")
    away_goals: Goals = Field(alias="AG")
    result: Result = Field(alias="Res")


class FootballDataCoUkClient:
    def __init__(self, session: requests.Session, limiter: RateLimiter) -> None:
        self._session = session
        self._limiter = limiter

    def fetch_season(self, division: str, season: int) -> bytes:
        """The file of a division season as sent; 2026 is in the folder 2627."""
        folder = f"{season % 100:02d}{(season + 1) % 100:02d}"
        return self._get(f"{BASE_URL}/mmz4281/{folder}/{division}.csv", f"{division} {season}")

    def fetch_extra_league(self, league: str) -> bytes:
        """The file with every season of an extra league, as sent."""
        return self._get(f"{BASE_URL}/new/{league}.csv", league)

    def _get(self, url: str, what: str) -> bytes:
        self._limiter.wait()
        try:
            response = self._session.get(url, timeout=TIMEOUT)
        except NETWORK_ERRORS as error:
            raise SourceError(f"football-data.co.uk did not answer for {what}: {error}") from error
        if not response.ok:
            raise SourceError(f"football-data.co.uk answered {response.status_code} for {what}")
        return response.content


def parse_division_season(body: bytes) -> list[dict[str, str]]:
    """The matches of a division season, each a row as sent, once they meet the contract."""
    return _parse(body, DivisionMatch, _DIVISION_MATCHES)


def parse_extra_league(body: bytes) -> list[dict[str, str]]:
    """The matches of every season of an extra league, as for a division season."""
    return _parse(body, ExtraLeagueMatch, _EXTRA_LEAGUE_MATCHES)


def split_matches(body: bytes) -> list[dict[str, str]]:
    """The matches of a stored file, which passed the contract when it was extracted.

    Not checked again: a stricter contract later on must not lock old runs out of a reload.
    """
    return list(_reader(body))


_DIVISION_MATCHES = TypeAdapter(list[DivisionMatch])
_EXTRA_LEAGUE_MATCHES = TypeAdapter(list[ExtraLeagueMatch])


def _parse(
    body: bytes, contract: type[_Contract], adapter: TypeAdapter[list[Any]]
) -> list[dict[str, str]]:
    try:
        reader = _reader(body)
        # A page that is not a CSV file has none of the columns, and so no rows to check.
        missing = {field.alias or name for name, field in contract.model_fields.items()} - set(
            reader.fieldnames or ()
        )
    except UnicodeDecodeError as error:
        raise SourceError(f"football-data.co.uk sent a file that is not UTF-8: {error}") from None
    if missing:
        raise SourceError(f"football-data.co.uk sent a file without columns {sorted(missing)}")
    matches = list(reader)
    try:
        adapter.validate_python(matches)
    except ValidationError as error:
        raise broken_contract("football-data.co.uk", "matches", error) from None
    return matches


def _reader(body: bytes) -> csv.DictReader[str]:
    # The files start with a byte order mark.
    return csv.DictReader(io.StringIO(body.decode("utf-8-sig")), restval="")
