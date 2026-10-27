with players as (
    select
        -- A roster names no match: the request did, and the path of its file keeps it.
        cast(regexp_extract(_gcs_uri, r'/match=(\d+)/') as int64) as match_id,
        cast(string(payload.player_id) as int64) as player_id,
        string(payload.player) as player_name,
        string(payload.team_id) as team_key,
        string(payload.h_a) = 'h' as is_home,
        string(payload.position) as position,
        cast(string(payload.time) as int64) as minutes,
        cast(string(payload.goals) as int64) as goals,
        cast(string(payload.own_goals) as int64) as own_goals,
        cast(string(payload.assists) as int64) as assists,
        cast(string(payload.shots) as int64) as shots,
        cast(string(payload.key_passes) as int64) as key_passes,
        cast(string(payload.xG) as float64) as xg,
        cast(string(payload.xA) as float64) as xa,
        cast(string(payload.yellow_card) as int64) as yellow_cards,
        cast(string(payload.red_card) as int64) as red_cards,
        _run_date as run_date,
        _loaded_at as loaded_at
    from {{ source('understat', 'match_players') }}
)

select *
from players
-- Rosters are fetched once, unless their file is removed; then the latest run counts.
qualify row_number() over (partition by match_id, player_id order by run_date desc) = 1
