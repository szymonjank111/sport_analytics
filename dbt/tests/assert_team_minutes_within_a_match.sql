-- Eleven players for 90 minutes at most, with a margin for minutes rounded at substitutions.
{{ config(severity='warn') }}

select
    understat_match_id,
    team_id,
    sum(minutes) as minutes
from {{ ref('fct_player_matches') }}
group by understat_match_id, team_id
having sum(minutes) > 11 * 90 * 1.05
