import json
from collections.abc import Callable
from typing import Any

import pytest
import requests

from fakes import PL_MATCHES, FakeAdapter, football_data_client
from sport_analytics.ingestion.errors import SourceError
from sport_analytics.ingestion.sources.football_data import parse_matches

Edit = Callable[[dict[str, Any]], object]

BREAKS: dict[str, Edit] = {
    "no id": lambda match: match.pop("id"),
    "id as text": lambda match: match.update(id="600001"),
    "unknown status": lambda match: match.update(status="ABANDONED"),
    "goals as text": lambda match: match["score"]["fullTime"].update(home="2"),
    "matchday as a flag": lambda match: match.update(matchday=True),
    "kick-off as a number": lambda match: match.update(utcDate=1787407200),
    "kick-off without a zone": lambda match: match.update(utcDate="2026-08-22T14:00:00"),
    "no kick-off": lambda match: match.update(utcDate=None),
}
KEEPS: dict[str, Edit] = {
    "a new field": lambda match: match.update(venue="Emirates Stadium"),
    "an unread field gone": lambda match: match.pop("group"),
    "extra time": lambda match: match.update(status="EXTRA_TIME"),
    "a tie still to be decided": lambda match: match["homeTeam"].update(id=None, name=None),
}


def with_first_match(edit: Edit) -> bytes:
    data = json.loads(PL_MATCHES)
    edit(data["matches"][0])
    return json.dumps(data).encode()


def test_parses_matches_as_sent() -> None:
    matches = parse_matches(PL_MATCHES)

    assert [match["status"] for match in matches] == ["FINISHED", "POSTPONED", "TIMED"]
    assert matches[0]["score"]["fullTime"] == {"home": 2, "away": 1}


@pytest.mark.parametrize(
    "body",
    [b"not json", b"\xff", b"[]", b'{"resultSet": {"count": 0}}', b'{"matches": [1]}'],
)
def test_refuses_a_body_without_a_list_of_matches(body: bytes) -> None:
    with pytest.raises(SourceError, match="contract"):
        parse_matches(body)


@pytest.mark.parametrize("edit", BREAKS.values(), ids=BREAKS.keys())
def test_refuses_a_match_that_breaks_the_contract(edit: Edit) -> None:
    with pytest.raises(SourceError, match=r"contract at matches\.0\.[^(]*$"):
        parse_matches(with_first_match(edit))


@pytest.mark.parametrize("edit", KEEPS.values(), ids=KEEPS.keys())
def test_accepts_a_match_within_the_contract_as_sent(edit: Edit) -> None:
    body = with_first_match(edit)

    assert parse_matches(body) == json.loads(body)["matches"]


def test_reports_a_broken_contract_on_one_line() -> None:
    data = json.loads(PL_MATCHES)
    for match in data["matches"]:
        match.pop("id")

    with pytest.raises(SourceError) as error:
        parse_matches(json.dumps(data).encode())

    assert str(error.value) == (
        "football-data.org broke the matches contract at matches.0.id: Field required (and 2 more)"
    )


def test_asks_for_the_season_with_the_token() -> None:
    adapter = FakeAdapter((200, PL_MATCHES))

    body = football_data_client(adapter).fetch_matches("PL", 2026)

    assert body == PL_MATCHES
    [request] = adapter.requests
    assert request.url == "https://api.football-data.org/v4/competitions/PL/matches?season=2026"
    assert request.headers["X-Auth-Token"] == "secret"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b'{"message": "Please check your subscription.", "errorCode": 403}', "subscription"),
        (b'{"error": "Please check your subscription."}', "subscription"),
        (b"<html>Forbidden</html>", "Forbidden"),
    ],
)
def test_an_error_answer_says_why(body: bytes, message: str) -> None:
    client = football_data_client(FakeAdapter((403, body)))

    with pytest.raises(SourceError, match=f"answered 403: .*{message}"):
        client.fetch_matches("PL", 2020)


def test_an_error_page_is_cut_short() -> None:
    client = football_data_client(FakeAdapter((502, b"<html>" + b"x" * 10_000 + b"</html>")))

    with pytest.raises(SourceError) as error:
        client.fetch_matches("PL", 2026)

    assert len(str(error.value)) < 300


@pytest.mark.parametrize(
    "failure",
    [
        requests.ConnectionError("Name or service not known"),
        requests.ReadTimeout("read"),
        requests.exceptions.ChunkedEncodingError("Connection broken: IncompleteRead"),
    ],
)
def test_a_source_out_of_reach_says_so(failure: requests.RequestException) -> None:
    client = football_data_client(FakeAdapter(failure))

    with pytest.raises(SourceError, match="did not answer"):
        client.fetch_matches("PL", 2026)


def test_a_fault_of_the_setup_keeps_its_traceback() -> None:
    client = football_data_client(FakeAdapter(requests.exceptions.InvalidHeader("bad token")))

    with pytest.raises(requests.exceptions.InvalidHeader):
        client.fetch_matches("PL", 2026)
