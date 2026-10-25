import json
from typing import Any, Literal

import requests
from pydantic import AliasChoices, AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from sport_analytics.ingestion.errors import SourceError
from sport_analytics.ingestion.http import TIMEOUT

BASE_URL = "https://api.football-data.org/v4"


class _Contract(BaseModel):
    """The fields the pipeline reads; any other may come and go without breaking it.

    Strict, so a changed type is refused here instead of failing later in dbt. A field that may
    be null may also be missing, which dbt reads as null too.
    """

    model_config = ConfigDict(alias_generator=to_camel, strict=True, extra="ignore", frozen=True)


class TeamRef(_Contract):
    # Null for a cup tie whose teams are still to be decided.
    id: int | None = None
    name: str | None = None


class ScoreLine(_Contract):
    home: int | None = None
    away: int | None = None


class Score(_Contract):
    full_time: ScoreLine
    half_time: ScoreLine


class Match(_Contract):
    id: int
    utc_date: AwareDatetime
    # The lookup table of the docs; the page of the match resource leaves out the last two.
    status: Literal[
        "SCHEDULED",
        "TIMED",
        "IN_PLAY",
        "PAUSED",
        "EXTRA_TIME",
        "PENALTY_SHOOTOUT",
        "FINISHED",
        "SUSPENDED",
        "POSTPONED",
        "CANCELLED",
        "AWARDED",
    ]
    matchday: int | None = None
    stage: str
    last_updated: AwareDatetime
    home_team: TeamRef
    away_team: TeamRef
    score: Score


class MatchesResponse(_Contract):
    matches: list[Match]


class _Error(BaseModel):
    # The docs show an "error" field, but the API answers with "message" (and "errorCode").
    message: str = Field(validation_alias=AliasChoices("message", "error"))


class FootballDataClient:
    def __init__(self, api_key: str, session: requests.Session) -> None:
        self._api_key = api_key
        self._session = session

    def fetch_matches(self, competition: str, season: int) -> bytes:
        """The body as sent, which the raw layer keeps unchanged."""
        try:
            response = self._session.get(
                f"{BASE_URL}/competitions/{competition}/matches",
                params={"season": season},
                headers={"X-Auth-Token": self._api_key},
                timeout=TIMEOUT,
            )
        # Only what the source is to blame for; a bad header or URL is a fault of the setup.
        except (
            requests.ConnectionError,
            requests.Timeout,
            requests.exceptions.ChunkedEncodingError,
        ) as error:
            raise SourceError(f"football-data.org did not answer: {error}") from error
        if not response.ok:
            raise SourceError(
                f"football-data.org answered {response.status_code}: {_error_message(response)}"
            )
        return response.content


def parse_matches(body: bytes) -> list[dict[str, Any]]:
    """The matches of a competition season, each as the source sent it.

    The models only check the contract: the raw layer keeps the records unchanged. The body is
    decoded twice, as strict validation of dates works on JSON text only.
    """
    try:
        MatchesResponse.model_validate_json(body)
    except ValidationError as error:
        # One line, not pydantic's own message, which lists every error over many lines.
        first, *others = error.errors()
        where = ".".join(str(part) for part in first["loc"]) or "the body"
        more = f" (and {len(others)} more)" if others else ""
        raise SourceError(
            f"football-data.org broke the matches contract at {where}: {first['msg']}{more}"
        ) from None
    return split_matches(body)


def split_matches(body: bytes) -> list[dict[str, Any]]:
    """The matches of a stored answer, which passed the contract when it was extracted.

    Not checked again: a stricter contract later on must not lock old runs out of a reload.
    """
    return json.loads(body)["matches"]


def _error_message(response: requests.Response) -> str:
    try:
        return _Error.model_validate_json(response.content).message
    except ValidationError:
        # Cut, as it may be a whole HTML page of a proxy.
        return response.text[:200]
