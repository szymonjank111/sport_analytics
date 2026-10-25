-- Division files and extra league files name the same values differently, hence the coalesces.
with matches as (
    select
        _competition as competition_code,
        -- An extra league file names the season of each row: 2026/2027, or 2026 in Brazil.
        coalesce(_season, cast(left(string(payload.Season), 4) as int64)) as season,
        -- 21/08/2026, or 21/08/17 in most divisions in 2017/18.
        case length(string(payload.Date))
            when 8 then parse_date('%d/%m/%y', string(payload.Date))
            else parse_date('%d/%m/%Y', string(payload.Date))
        end as match_date,
        -- The files name teams and have no IDs, so the name is the key.
        coalesce(string(payload.HomeTeam), string(payload.Home)) as home_team_key,
        coalesce(string(payload.AwayTeam), string(payload.Away)) as away_team_key,
        -- safe_cast, since a value may be empty: the goals of a match never played, statistics
        -- a league or a season does not have.
        safe_cast(coalesce(string(payload.FTHG), string(payload.HG)) as int64) as home_goals,
        safe_cast(coalesce(string(payload.FTAG), string(payload.AG)) as int64) as away_goals,
        nullif(coalesce(string(payload.FTR), string(payload.Res)), '') as result,
        safe_cast(string(payload.HTHG) as int64) as home_goals_half_time,
        safe_cast(string(payload.HTAG) as int64) as away_goals_half_time,
        safe_cast(string(payload.HS) as int64) as home_shots,
        -- AS is a keyword, so this field needs the subscript.
        safe_cast(string(payload['AS']) as int64) as away_shots,
        safe_cast(string(payload.HST) as int64) as home_shots_on_target,
        safe_cast(string(payload.AST) as int64) as away_shots_on_target,
        safe_cast(string(payload.HC) as int64) as home_corners,
        safe_cast(string(payload.AC) as int64) as away_corners,
        safe_cast(string(payload.HF) as int64) as home_fouls,
        safe_cast(string(payload.AF) as int64) as away_fouls,
        safe_cast(string(payload.HY) as int64) as home_yellow_cards,
        safe_cast(string(payload.AY) as int64) as away_yellow_cards,
        safe_cast(string(payload.HR) as int64) as home_red_cards,
        safe_cast(string(payload.AR) as int64) as away_red_cards,
        safe_cast(string(payload.HxG) as float64) as home_xg,
        safe_cast(string(payload.AxG) as float64) as away_xg,
        nullif(string(payload.Referee), '') as referee,
        _run_date as run_date
    from {{ source('football_data_co_uk', 'matches') }}
)

select *
from matches
-- Each file holds a whole season, so the latest run that fetched a season has its current state.
-- That needs no key for a match, which the files lack: a pair met at home twice in a season of
-- the Ekstraklasa while it split into groups (until 2020).
qualify run_date = max(run_date) over (partition by competition_code, season)
