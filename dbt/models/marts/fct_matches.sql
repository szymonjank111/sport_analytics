select
    match_id,
    competition_code,
    season,
    matchday,
    kickoff_at,
    date(kickoff_at) as match_date,
    status,
    home_team_name,
    away_team_name,
    home_goals,
    away_goals
from {{ ref('stg_football_data__matches') }}
