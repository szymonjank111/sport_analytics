with matches as (
    select
        cast(string(payload.id) as int64) as match_id,
        _competition as competition_code,
        _season as season,
        -- In UTC: Liverpool's 20:00 BST kick-off on 15 August 2025 reads 19:00.
        timestamp(string(payload.datetime)) as kickoff_at,
        bool(payload.isResult) as has_result,
        string(payload.h.id) as home_team_key,
        string(payload.h.title) as home_team_name,
        string(payload.a.id) as away_team_key,
        string(payload.a.title) as away_team_name,
        -- Numbers come as text, and as JSON null before kick-off, which string() refuses.
        cast(lax_string(payload.goals.h) as int64) as home_goals,
        cast(lax_string(payload.goals.a) as int64) as away_goals,
        cast(lax_string(payload.xG.h) as float64) as home_xg,
        cast(lax_string(payload.xG.a) as float64) as away_xg,
        _run_date as run_date
    from {{ source('understat', 'league_matches') }}
)

select *
from matches
-- Each run snapshots the whole season, so the latest one has the current state of a match.
qualify row_number() over (partition by match_id order by run_date desc) = 1
