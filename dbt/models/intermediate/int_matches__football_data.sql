with team_mapping as (
    select
        source_team_key,
        team_id
    from {{ ref('team_mapping') }}
    where source = 'football_data'
)

select
    competitions.competition_id,
    matches.season,
    matches.matchday,
    matches.kickoff_at,
    date(matches.kickoff_at) as match_date,
    case
        when matches.status in ('scheduled', 'timed') then 'scheduled'
        when
            matches.status in ('in_play', 'paused', 'extra_time', 'penalty_shootout')
            then 'in_play'
        else matches.status
    end as status,
    home_teams.team_id as home_team_id,
    away_teams.team_id as away_team_id,
    matches.home_goals,
    matches.away_goals,
    matches.match_id as football_data_match_id
from {{ ref('stg_football_data__matches') }} as matches
inner join {{ ref('competitions') }} as competitions
    on matches.competition_code = competitions.football_data_code
-- Inner joins drop cup ties still to be decided; assert_all_teams_mapped makes sure that they
-- drop nothing else.
inner join team_mapping as home_teams
    on matches.home_team_key = home_teams.source_team_key
inner join team_mapping as away_teams
    on matches.away_team_key = away_teams.source_team_key
