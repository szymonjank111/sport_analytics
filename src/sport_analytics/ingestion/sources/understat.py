import json
from typing import Annotated, Any, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from sport_analytics.ingestion.errors import SourceError, broken_contract
from sport_analytics.ingestion.http import NETWORK_ERRORS, TIMEOUT
from sport_analytics.ingestion.rate_limit import RateLimiter

BASE_URL = "https://understat.com"
LEAGUES = ("EPL", "La_liga", "Bundesliga", "Serie_A", "Ligue_1")
"""The top five leagues; Understat also covers the Russian one, which the project leaves out."""
MIN_INTERVAL = 3.0
"""Seconds between requests: the site asks robots to stay away, so the pace is slow."""

# Understat sends numbers as text.
Whole = Annotated[str, StringConstraints(pattern=r"^\d+$")]
Decimal = Annotated[str, StringConstraints(pattern=r"^\d+(\.\d+)?$")]
Name = Annotated[str, StringConstraints(min_length=1)]
# 2026-08-21 19:00:00, in UTC.
KickOff = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")]


class _Contract(BaseModel):
    """The fields the pipeline reads; any other may come and go without breaking it."""

    model_config = ConfigDict(strict=True, extra="ignore", frozen=True)


class Team(_Contract):
    id: Whole
    title: Name


# Goals and xG are null until the match is played.
class Goals(_Contract):
    h: Whole | None
    a: Whole | None


class Xg(_Contract):
    h: Decimal | None
    a: Decimal | None


class LeagueMatch(_Contract):
    id: Whole
    is_result: bool = Field(alias="isResult")
    h: Team
    a: Team
    goals: Goals
    xg: Xg = Field(alias="xG")
    kickoff: KickOff = Field(alias="datetime")


class League(_Contract):
    dates: list[LeagueMatch]


class RosterPlayer(_Contract):
    player_id: Whole
    player: Name
    team_id: Whole
    h_a: Literal["h", "a"]
    position: Name
    time: Whole
    goals: Whole
    own_goals: Whole
    assists: Whole
    shots: Whole
    key_passes: Whole
    xg: Decimal = Field(alias="xG")
    xa: Decimal = Field(alias="xA")
    yellow_card: Whole
    red_card: Whole


class Rosters(_Contract):
    h: dict[str, RosterPlayer]
    a: dict[str, RosterPlayer]


class Match(_Contract):
    rosters: Rosters


class UnderstatClient:
    def __init__(self, session: requests.Session, limiter: RateLimiter) -> None:
        self._session = session
        self._limiter = limiter

    def fetch_league(self, league: str, season: int) -> bytes:
        """The matches, teams and players of a league season, as sent."""
        return self._get(f"getLeagueData/{league}/{season}", f"{league} {season}")

    def fetch_match(self, match_id: int) -> bytes:
        """The rosters and shots of a match, as sent."""
        return self._get(f"getMatchData/{match_id}", f"match {match_id}")

    def _get(self, path: str, what: str) -> bytes:
        self._limiter.wait()
        try:
            # The site answers the requests of its own pages only: without the header, 404.
            response = self._session.get(
                f"{BASE_URL}/{path}",
                headers={"X-Requested-With": "XMLHttpRequest"},
                timeout=TIMEOUT,
            )
        except NETWORK_ERRORS as error:
            raise SourceError(f"Understat did not answer for {what}: {error}") from error
        if not response.ok:
            raise SourceError(f"Understat answered {response.status_code} for {what}")
        return response.content


def parse_league(body: bytes) -> list[dict[str, Any]]:
    """The matches of a league season, each as sent, once they meet the contract."""
    try:
        league = League.model_validate_json(body)
    except ValidationError as error:
        raise broken_contract("Understat", "league_matches", error) from None
    if not league.dates:
        # Stored, an empty season would count as fetched and never be asked for again.
        raise SourceError("Understat has no matches for the league season")
    return split_league_matches(body)


def parse_match_players(body: bytes) -> list[dict[str, Any]]:
    """The players of both rosters of a match, each as sent, once they meet the contract."""
    try:
        Match.model_validate_json(body)
    except ValidationError as error:
        raise broken_contract("Understat", "match_players", error) from None
    return split_match_players(body)


def split_league_matches(body: bytes) -> list[dict[str, Any]]:
    """The matches of a stored answer, which passed the contract when it was extracted.

    Not checked again: a stricter contract later on must not lock old runs out of a reload.
    """
    return json.loads(body)["dates"]


def split_match_players(body: bytes) -> list[dict[str, Any]]:
    """The players of a stored answer, as for the matches of a league season."""
    rosters = json.loads(body)["rosters"]
    return [*rosters["h"].values(), *rosters["a"].values()]
