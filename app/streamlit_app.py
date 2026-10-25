from typing import cast

import pandas as pd
import streamlit as st
from google.cloud import bigquery

from sport_analytics.settings import get_app_settings

st.set_page_config(page_title="Football Analytics", layout="wide")


@st.cache_data(ttl=3600)
def load_matches() -> pd.DataFrame:
    settings = get_app_settings()
    client = bigquery.Client(project=settings.gcp_project_id, location=settings.gcp_location)
    # A table name cannot be a query parameter; this one comes from trusted settings.
    dataset = f"{settings.gcp_project_id}.{settings.app_dataset}"
    query = f"""
        select matches.season, matches.matchday, matches.kickoff_at, matches.match_date,
            matches.status, home.name as home_team_name, away.name as away_team_name,
            matches.home_goals, matches.away_goals
        from `{dataset}.fct_matches` as matches
        join `{dataset}.dim_teams` as home on matches.home_team_id = home.team_id
        join `{dataset}.dim_teams` as away on matches.away_team_id = away.team_id
    """
    # BigQuery imports pandas as an optional dependency, which pyright cannot resolve.
    return cast(pd.DataFrame, client.query(query).to_dataframe())  # pyright: ignore[reportUnknownMemberType]


def season_label(season: int) -> str:
    return f"{season}/{(season + 1) % 100:02d}"


def goals_by_team(played: pd.DataFrame) -> pd.DataFrame:
    sides = [
        played[[f"{side}_team_name", f"{side}_goals"]].set_axis(["team", "goals"], axis=1)
        for side in ("home", "away")
    ]
    return pd.concat(sides).groupby("team")["goals"].sum().reset_index()


st.title("Football Analytics")

matches = load_matches()
seasons = sorted(matches["season"].unique().tolist(), reverse=True)
season = st.selectbox("Season", seasons, format_func=season_label)
played = matches[(matches["season"] == season) & (matches["status"] == "finished")]

if played.empty:
    st.info("No matches of this season have been played yet.")
    st.stop()

latest, goals = st.columns(2)
with latest:
    st.subheader("Latest results")
    # Streamlit's type of data refers to pyarrow, which has no type information.
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
with goals:
    st.subheader("Goals scored")
    st.bar_chart(  # pyright: ignore[reportUnknownMemberType]
        goals_by_team(played), x="team", y="goals", horizontal=True, sort="-goals"
    )
