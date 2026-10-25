select
    int64(payload.id) as match_id,
    _competition as competition_code,
    _season as season,
    -- lax_ for what may be JSON null, which int64() and string() refuse: the matchday in cups,
    -- the teams of a tie still to be decided, the score before kick-off.
    lax_int64(payload.matchday) as matchday,
    string(payload.stage) as stage,
    lower(string(payload.status)) as status,
    timestamp(string(payload.utcDate)) as kickoff_at,
    lax_string(payload.homeTeam.id) as home_team_key,
    lax_string(payload.homeTeam.name) as home_team_name,
    lax_string(payload.awayTeam.id) as away_team_key,
    lax_string(payload.awayTeam.name) as away_team_name,
    lax_int64(payload.score.fullTime.home) as home_goals,
    lax_int64(payload.score.fullTime.away) as away_goals,
    lax_int64(payload.score.halfTime.home) as home_goals_half_time,
    lax_int64(payload.score.halfTime.away) as away_goals_half_time,
    timestamp(string(payload.lastUpdated)) as last_updated_at,
    _run_date as run_date
from {{ source('football_data', 'matches') }}
-- Each run snapshots the whole season, so the latest one has the current state of a match.
qualify row_number() over (partition by int64(payload.id) order by _run_date desc) = 1
