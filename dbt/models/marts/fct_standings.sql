with league_matches as (
    select matches.*
    from {{ ref('fct_matches') }} as matches
    inner join {{ ref('dim_competitions') }} as competitions
        on matches.competition_id = competitions.competition_id
    where competitions.competition_type = 'league'
),

-- The teams of league seasons only, which also keeps the rounds of cups out of the grid below.
season_teams as (
    select
        competition_id,
        season,
        home_team_id as team_id
    from league_matches
    union distinct
    select
        competition_id,
        season,
        away_team_id
    from league_matches
),

played_matchdays as (
    select distinct
        competition_id,
        season,
        matchday
    from {{ ref('fct_team_matches') }}
),

-- Every team in every round, so that a team whose match was postponed keeps its place.
matchday_results as (
    select
        season_teams.competition_id,
        season_teams.season,
        played_matchdays.matchday,
        season_teams.team_id,
        count(team_matches.match_key) as played,
        countif(team_matches.result = 'W') as wins,
        countif(team_matches.result = 'D') as draws,
        countif(team_matches.result = 'L') as losses,
        coalesce(sum(team_matches.goals_for), 0) as goals_for,
        coalesce(sum(team_matches.goals_against), 0) as goals_against,
        coalesce(sum(team_matches.points), 0) as points
    from season_teams
    inner join played_matchdays
        on
            season_teams.competition_id = played_matchdays.competition_id
            and season_teams.season = played_matchdays.season
    left join {{ ref('fct_team_matches') }} as team_matches
        on
            season_teams.competition_id = team_matches.competition_id
            and season_teams.season = team_matches.season
            and played_matchdays.matchday = team_matches.matchday
            and season_teams.team_id = team_matches.team_id
    group by 1, 2, 3, 4
),

running_totals as (
    select
        competition_id,
        season,
        matchday,
        team_id,
        sum(played) over team_rounds as played,
        sum(wins) over team_rounds as wins,
        sum(draws) over team_rounds as draws,
        sum(losses) over team_rounds as losses,
        sum(goals_for) over team_rounds as goals_for,
        sum(goals_against) over team_rounds as goals_against,
        sum(goals_for - goals_against) over team_rounds as goal_difference,
        sum(points) over team_rounds as points
    from matchday_results
    window team_rounds as (partition by competition_id, season, team_id order by matchday)
)

select
    *,
    rank() over (
        partition by competition_id, season, matchday
        order by points desc, goal_difference desc, goals_for desc
    ) as position
from running_totals
