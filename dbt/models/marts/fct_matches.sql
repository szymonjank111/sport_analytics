select
    {{ dbt_utils.generate_surrogate_key(
        ['competition_id', 'season', 'home_team_id', 'away_team_id']
    ) }} as match_key,
    competition_id,
    season,
    matchday,
    kickoff_at,
    match_date,
    status,
    home_team_id,
    away_team_id,
    home_goals,
    away_goals,
    case
        when status not in ('finished', 'awarded') then null
        when home_goals > away_goals then 'H'
        when home_goals < away_goals then 'A'
        else 'D'
    end as result,
    football_data_match_id
from {{ ref('int_matches__football_data') }}
