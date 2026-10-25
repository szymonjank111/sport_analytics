import pytest

from fakes import PL_MATCHES, FakeAdapter, football_data_client
from sport_analytics.ingestion.errors import SourceError
from sport_analytics.ingestion.sources.football_data import parse_matches


def test_parses_matches_as_sent() -> None:
    matches = parse_matches(PL_MATCHES)

    assert [match["status"] for match in matches] == ["FINISHED", "POSTPONED", "TIMED"]
    assert matches[0]["score"]["fullTime"] == {"home": 2, "away": 1}


@pytest.mark.parametrize(
    "body",
    [b"not json", b"\xff", b"[]", b'{"resultSet": {"count": 0}}', b'{"matches": [1]}'],
)
def test_refuses_a_body_without_a_list_of_matches(body: bytes) -> None:
    with pytest.raises(SourceError, match="no list of matches"):
        parse_matches(body)


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
