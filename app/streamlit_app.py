from typing import cast

import pandas as pd
import streamlit as st
from google.cloud import bigquery

from sport_analytics.settings import get_app_settings

st.set_page_config(page_title="Football Analytics", layout="wide")


@st.cache_data(ttl=3600)
def run_query(query: str) -> pd.DataFrame:
    settings = get_app_settings()
    client = bigquery.Client(project=settings.gcp_project_id, location=settings.gcp_location)
    # BigQuery imports pandas as an optional dependency, which pyright cannot resolve.
    return cast(pd.DataFrame, client.query(query).to_dataframe())  # pyright: ignore[reportUnknownMemberType]


def season_label(season: int, calendar_year: bool) -> str:
    return str(season) if calendar_year else f"{season}/{(season + 1) % 100:02d}"


settings = get_app_settings()
# A table name cannot be a query parameter; this one comes from trusted settings.
dataset = f"{settings.gcp_project_id}.{settings.app_dataset}"
competitions = run_query(f"""
    select competition_id, name, competition_type, season_calendar
    from `{dataset}.dim_competitions`
    order by country is null, country, tier
""")
matches = run_query(f"""
    select matches.competition_id, matches.season, matches.stage, matches.matchday,
        matches.kickoff_at, matches.match_date,
        home.name as home_team_name, away.name as away_team_name,
        matches.home_goals, matches.away_goals, matches.result
    from `{dataset}.fct_matches` as matches
    join `{dataset}.dim_teams` as home on matches.home_team_id = home.team_id
    join `{dataset}.dim_teams` as away on matches.away_team_id = away.team_id
""")
standings = run_query(f"""
    select standings.*, teams.name as team_name
    from `{dataset}.fct_standings` as standings
    join `{dataset}.dim_teams` as teams using (team_id)
""")

st.title("Football Analytics")

covered = competitions[competitions["competition_id"].isin(matches["competition_id"])]
if covered.empty:
    st.info("No matches have been loaded yet.")
    st.stop()
names = dict(zip(covered["competition_id"], covered["name"], strict=True))
competition_id = st.selectbox(
    "Competition",
    covered["competition_id"].tolist(),
    format_func=lambda competition_id: names[competition_id],
)
competition = covered[covered["competition_id"] == competition_id].iloc[0]
is_league = competition["competition_type"] == "league"
calendar_year = competition["season_calendar"] == "calendar"

competition_matches = matches[matches["competition_id"] == competition_id]
seasons = sorted(competition_matches["season"].unique().tolist(), reverse=True)
season = st.selectbox(
    "Season", seasons, format_func=lambda season: season_label(season, calendar_year)
)
played = competition_matches[
    (competition_matches["season"] == season) & competition_matches["result"].notna()
]

if played.empty:
    st.info("No matches of this season have been played yet.")
    st.stop()

if is_league:
    league, latest = st.columns([3, 2])
    with league:
        season_standings = standings[
            (standings["competition_id"] == competition_id) & (standings["season"] == season)
        ]
        last_round = int(season_standings["matchday"].max())
        table = season_standings[season_standings["matchday"] == last_round]
        st.subheader("League table")
        st.caption(f"After round {last_round}")
        # Streamlit's type of data refers to pyarrow, which has no type information.
        st.dataframe(  # pyright: ignore[reportUnknownMemberType]
            table.sort_values(["position", "team_name"]),
            hide_index=True,
            column_order=[
                "position",
                "team_name",
                "played",
                "wins",
                "draws",
                "losses",
                "goals_for",
                "goals_against",
                "goal_difference",
                "points",
            ],
            column_config={
                "position": "#",
                "team_name": "Team",
                "played": "P",
                "wins": "W",
                "draws": "D",
                "losses": "L",
                "goals_for": "GF",
                "goals_against": "GA",
                "goal_difference": "GD",
                "points": "Pts",
            },
        )
else:
    latest = st.container()

with latest:
    st.subheader("Latest results")
    # Knockout ties have a stage instead of a round.
    round_column = "matchday" if is_league else "stage"
    st.dataframe(  # pyright: ignore[reportUnknownMemberType]
        played.sort_values("kickoff_at", ascending=False).assign(
            score=played["home_goals"].astype(str) + "-" + played["away_goals"].astype(str)
        ),
        hide_index=True,
        column_order=["match_date", round_column, "home_team_name", "score", "away_team_name"],
        column_config={
            "match_date": "Date",
            "matchday": "Round",
            "stage": "Stage",
            "home_team_name": "Home",
            "score": "Score",
            "away_team_name": "Away",
        },
    )
