import pytest
import requests

from fakes import E0_SEASON, POL_SEASONS, FakeAdapter, football_data_co_uk_client
from sport_analytics.ingestion.errors import SourceError
from sport_analytics.ingestion.sources.football_data_co_uk import (
    parse_division_season,
    parse_extra_league,
    split_matches,
)


def with_first_row(body: bytes, old: str, new: str) -> bytes:
    header, first, *rest = body.decode("utf-8-sig").splitlines()
    return "\n".join([header, first.replace(old, new, 1), *rest]).encode()


def test_parses_the_rows_of_a_division_season_as_sent() -> None:
    matches = parse_division_season(E0_SEASON)

    assert [match["HomeTeam"] for match in matches] == ["Arsenal", "Everton", "Hull"]
    assert matches[0]["Div"] == "E0"
    assert matches[0]["AvgCH"] == "1.22"


def test_parses_an_extra_league_with_a_match_never_played() -> None:
    matches = parse_extra_league(POL_SEASONS)

    assert [match["Season"] for match in matches] == ["2025/2026", "2026/2027", "2026/2027"]
    assert (matches[2]["HG"], matches[2]["Res"]) == ("", "")


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("21/08/2026", "2026-08-21"),
        ("Arsenal", ""),
        (",2,0,H,", ",two,0,H,"),
        (",2,0,H,", ",2,0,W,"),
    ],
    ids=["an ISO date", "no home team", "goals as words", "an unknown result"],
)
def test_refuses_a_row_that_breaks_the_contract(old: str, new: str) -> None:
    with pytest.raises(SourceError, match=r"broke the matches contract at 0\."):
        parse_division_season(with_first_row(E0_SEASON, old, new))


def test_accepts_a_two_digit_year() -> None:
    body = with_first_row(E0_SEASON, "21/08/2026", "21/08/26")

    assert parse_division_season(body)[0]["Date"] == "21/08/26"


def test_refuses_a_page_that_is_not_a_file_of_matches() -> None:
    with pytest.raises(SourceError, match="without columns"):
        parse_division_season(b"<html><body>Not found</body></html>")


def test_refuses_a_file_of_the_other_kind() -> None:
    with pytest.raises(SourceError, match=r"without columns \['AwayTeam', 'FTAG'"):
        parse_division_season(POL_SEASONS)


def test_refuses_a_file_that_is_not_utf_8() -> None:
    with pytest.raises(SourceError, match="not UTF-8"):
        parse_division_season(E0_SEASON.replace(b"Arsenal", b"Arsenal \xe9"))


def test_splits_a_stored_file_without_checking_it_again() -> None:
    body = with_first_row(E0_SEASON, "21/08/2026", "2026-08-21")

    assert split_matches(body)[0]["Date"] == "2026-08-21"


def test_asks_for_the_folder_of_the_season() -> None:
    adapter = FakeAdapter((200, E0_SEASON), (200, POL_SEASONS))
    client = football_data_co_uk_client(adapter)

    client.fetch_season("E0", 2026)
    client.fetch_extra_league("POL")

    assert [request.url for request in adapter.requests] == [
        "https://football-data.co.uk/mmz4281/2627/E0.csv",
        "https://football-data.co.uk/new/POL.csv",
    ]


def test_an_error_answer_says_what_was_asked_for() -> None:
    client = football_data_co_uk_client(FakeAdapter((404, b"<html>Not Found</html>")))

    with pytest.raises(SourceError, match="answered 404 for E0 2030"):
        client.fetch_season("E0", 2030)


def test_a_source_out_of_reach_says_so() -> None:
    client = football_data_co_uk_client(FakeAdapter(requests.ConnectionError("refused")))

    with pytest.raises(SourceError, match="did not answer for POL"):
        client.fetch_extra_league("POL")
