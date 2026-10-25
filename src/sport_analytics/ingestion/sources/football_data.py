from typing import Any

import requests
from pydantic import AliasChoices, BaseModel, Field, ValidationError

from sport_analytics.ingestion.errors import SourceError

BASE_URL = "https://api.football-data.org/v4"
TIMEOUT = (5, 30)
"""Seconds to connect and to wait for each read."""


class _Matches(BaseModel):
    matches: list[dict[str, Any]]


class _Error(BaseModel):
    # The docs show an "error" field, but the API answers with "message" (and "errorCode").
    message: str = Field(validation_alias=AliasChoices("message", "error"))


class FootballDataClient:
    def __init__(self, api_key: str, session: requests.Session) -> None:
        self._api_key = api_key
        self._session = session

    def fetch_matches(self, competition: str, season: int) -> bytes:
        """The body as sent, which the raw layer keeps unchanged."""
        response = self._session.get(
            f"{BASE_URL}/competitions/{competition}/matches",
            params={"season": season},
            headers={"X-Auth-Token": self._api_key},
            timeout=TIMEOUT,
        )
        if not response.ok:
            raise SourceError(
                f"football-data.org answered {response.status_code}: {_error_message(response)}"
            )
        return response.content


def parse_matches(body: bytes) -> list[dict[str, Any]]:
    """The matches of a competition season, each as the source sent it."""
    try:
        return _Matches.model_validate_json(body).matches
    except ValidationError as error:
        raise SourceError(f"football-data.org sent no list of matches: {error}") from error


def _error_message(response: requests.Response) -> str:
    try:
        return _Error.model_validate_json(response.content).message
    except ValidationError:
        # Cut, as it may be a whole HTML page of a proxy.
        return response.text[:200]
