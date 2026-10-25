with football_data_teams as (
    select
        home_team_key as team_key,
        home_team_name as team_name,
        competition_code
    from {{ ref('stg_football_data__matches') }}
    union all
    select
        away_team_key,
        away_team_name,
        competition_code
    from {{ ref('stg_football_data__matches') }}
),

football_data_co_uk_teams as (
    select
        home_team_key as team_key,
        competition_code
    from {{ ref('stg_football_data_co_uk__matches') }}
    union all
    select
        away_team_key,
        competition_code
    from {{ ref('stg_football_data_co_uk__matches') }}
),

source_teams as (
    select
        'football_data' as source,
        teams.team_key,
        any_value(teams.team_name) as team_name,
        any_value(competitions.country) as country
    from football_data_teams as teams
    left join {{ ref('competitions') }} as competitions
        on teams.competition_code = competitions.football_data_code
    -- A cup tie still to be decided has no teams yet.
    where teams.team_key is not null
    group by teams.team_key
    union all
    select
        'football_data_co_uk' as source,
        teams.team_key,
        teams.team_key as team_name,
        any_value(competitions.country) as country
    from football_data_co_uk_teams as teams
    left join {{ ref('competitions') }} as competitions
        on teams.competition_code = competitions.co_uk_code
    group by teams.team_key
)

select source_teams.*
from source_teams
left join {{ ref('team_mapping') }} as team_mapping
    on
        source_teams.source = team_mapping.source
        and source_teams.team_key = team_mapping.source_team_key
where team_mapping.team_id is null
