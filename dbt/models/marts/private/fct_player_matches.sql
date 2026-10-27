with player_matches as (
    select
        competitions.competition_id,
        matches.season,
        date(matches.kickoff_at) as match_date,
        players.match_id as understat_match_id,
        players.player_id as understat_player_id,
        players.player_name,
        teams.team_id,
        players.is_home,
        players.position,
        players.minutes,
        players.goals,
        players.own_goals,
        players.assists,
        players.shots,
        players.key_passes,
        players.xg,
        players.xa,
        players.yellow_cards,
        players.red_cards,
        players.loaded_at
    from {{ ref('stg_understat__player_matches') }} as players
    inner join {{ ref('stg_understat__matches') }} as matches
        on players.match_id = matches.match_id
    inner join {{ ref('competitions') }} as competitions
        on matches.competition_code = competitions.understat_code
    -- assert_all_teams_mapped makes sure that the inner join drops no player.
    inner join {{ ref('team_mapping') }} as teams
        on
            teams.source = 'understat'
            and players.team_key = teams.source_team_key
)

select *
from player_matches
{% if is_incremental() %}
    -- insert_overwrite replaces whole months, so a month with any rosters loaded since the last
    -- build is selected whole, older ones included, as a backfill of past seasons loads them.
    where date_trunc(player_matches.match_date, month) in (
        select date_trunc(new_rows.match_date, month)
        from player_matches as new_rows
        where new_rows.loaded_at > (select max(built.loaded_at) from {{ this }} as built)
    )
{% endif %}
