import json

import pytest
import requests

from fakes import EPL_SEASON, MATCH_ROSTERS, FakeAdapter, understat_client
from sport_analytics.ingestion.errors import SourceError
from sport_analytics.ingestion.sources.understat import (
    parse_league,
    parse_match_players,
    split_league_matches,
)


def edited(body: bytes, old: str, new: str) -> bytes:
    return body.replace(old.encode(), new.encode(), 1)


def test_parses_the_matches_of_a_league_season_as_sent() -> None:
    matches = parse_league(EPL_SEASON)

    assert [match["id"] for match in matches] == ["90001", "90002", "90003"]
    assert matches[0]["forecast"]["w"] == "0.7012"
    assert matches[2]["xG"] == {"h": None, "a": None}


def test_parses_the_players_of_both_rosters() -> None:
    players = parse_match_players(MATCH_ROSTERS)

    assert [player["player_id"] for player in players] == ["5001", "5002", "5003", "6001", "6002"]
    assert players[1]["xGChain"] == "1.5112"


@pytest.mark.parametrize(
    ("old", "new", "where"),
    [
        ('"isResult": true', '"isResult": "true"', "dates.0.isResult"),
        ('"1.74213"', "1.74213", "dates.0.xG.h"),
        ('"2026-08-21 19:00:00"', '"2026-08-21"', "dates.0.datetime"),
        ('"id": "83"', '"id": "ARS"', "dates.0.h.id"),
    ],
    ids=["a flag as text", "xG as a number", "a date without time", "a team without an ID"],
)
def test_refuses_a_league_season_that_breaks_the_contract(old: str, new: str, where: str) -> None:
    with pytest.raises(SourceError, match=rf"broke the league_matches contract at {where}:"):
        parse_league(edited(EPL_SEASON, old, new))


@pytest.mark.parametrize(
    ("old", "new", "where"),
    [
        ('"time": "90"', '"time": "90\'"', "rosters.h.700001.time"),
        ('"xG": "1.3307"', '"xG": "-0.1"', "rosters.h.700002.xG"),
        ('"h_a": "a"', '"h_a": "away"', "rosters.a.700004.h_a"),
    ],
    ids=["minutes with a mark", "negative xG", "an unknown side"],
)
def test_refuses_rosters_that_break_the_contract(old: str, new: str, where: str) -> None:
    with pytest.raises(SourceError, match=rf"broke the match_players contract at {where}:"):
        parse_match_players(edited(MATCH_ROSTERS, old, new))


def test_refuses_a_season_without_matches() -> None:
    with pytest.raises(SourceError, match="no matches"):
        parse_league(b'{"teams": [], "players": [], "dates": []}')


def test_refuses_a_page_that_is_not_json() -> None:
    with pytest.raises(SourceError, match="at the body"):
        parse_league(b"<html>404 Page Not Found</html>")


def test_splits_a_stored_answer_without_checking_it_again() -> None:
    body = json.dumps({"dates": [{"id": "1", "isResult": "maybe"}]}).encode()

    assert split_league_matches(body) == [{"id": "1", "isResult": "maybe"}]


def test_asks_as_the_pages_of_the_site_do() -> None:
    adapter = FakeAdapter((200, EPL_SEASON), (200, MATCH_ROSTERS))
    client = understat_client(adapter)

    client.fetch_league("EPL", 2026)
    client.fetch_match(90001)

    assert [request.url for request in adapter.requests] == [
        "https://understat.com/getLeagueData/EPL/2026",
        "https://understat.com/getMatchData/90001",
    ]
    assert {request.headers["X-Requested-With"] for request in adapter.requests} == {
        "XMLHttpRequest"
    }


def test_an_error_answer_says_what_was_asked_for() -> None:
    client = understat_client(FakeAdapter((404, b"<html>404 Page Not Found</html>")))

    with pytest.raises(SourceError, match="answered 404 for EPL 2010"):
        client.fetch_league("EPL", 2010)


def test_a_source_out_of_reach_says_so() -> None:
    client = understat_client(FakeAdapter(requests.ConnectionError("refused")))

    with pytest.raises(SourceError, match="did not answer for match 90001"):
        client.fetch_match(90001)
