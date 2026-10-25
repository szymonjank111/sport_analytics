with played as (
    select *
    from {{ ref('fct_matches') }}
    where result is not null
),

team_matches as (
    select
        match_key,
        home_team_id as team_id,
        away_team_id as opponent_id,
        true as is_home,
        competition_id,
        season,
        matchday,
        match_date,
        home_goals as goals_for,
        away_goals as goals_against
    from played
    union all
    select
        match_key,
        away_team_id as team_id,
        home_team_id as opponent_id,
        false as is_home,
        competition_id,
        season,
        matchday,
        match_date,
        away_goals as goals_for,
        home_goals as goals_against
    from played
)

select
    match_key,
    team_id,
    opponent_id,
    is_home,
    competition_id,
    season,
    matchday,
    match_date,
    goals_for,
    goals_against,
    case
        when goals_for > goals_against then 'W'
        when goals_for = goals_against then 'D'
        else 'L'
    end as result,
    case
        when goals_for > goals_against then 3
        when goals_for = goals_against then 1
        else 0
    end as points
from team_matches
