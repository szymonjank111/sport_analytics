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


def season_label(season: int) -> str:
    return f"{season}/{(season + 1) % 100:02d}"


settings = get_app_settings()
# A table name cannot be a query parameter; this one comes from trusted settings.
dataset = f"{settings.gcp_project_id}.{settings.app_dataset}"
matches = run_query(f"""
    select matches.season, matches.matchday, matches.kickoff_at, matches.match_date,
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

seasons = sorted(matches["season"].unique().tolist(), reverse=True)
season = st.selectbox("Season", seasons, format_func=season_label)
played = matches[(matches["season"] == season) & matches["result"].notna()]

if played.empty:
    st.info("No matches of this season have been played yet.")
    st.stop()

season_standings = standings[standings["season"] == season]
last_round = int(season_standings["matchday"].max())
table = season_standings[season_standings["matchday"] == last_round]

league, latest = st.columns([3, 2])
with league:
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
with latest:
    st.subheader("Latest results")
    st.dataframe(  # pyright: ignore[reportUnknownMemberType]
        played.sort_values("kickoff_at", ascending=False).assign(
            score=played["home_goals"].astype(str) + "-" + played["away_goals"].astype(str)
        ),
        hide_index=True,
        column_order=["match_date", "matchday", "home_team_name", "score", "away_team_name"],
        column_config={
            "match_date": "Date",
            "matchday": "Round",
            "home_team_name": "Home",
            "score": "Score",
            "away_team_name": "Away",
        },
    )
