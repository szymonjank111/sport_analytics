select
    matches.match_key,
    count(team_matches.match_key) as team_rows
from {{ ref('fct_matches') }} as matches
left join {{ ref('fct_team_matches') }} as team_matches
    on matches.match_key = team_matches.match_key
where matches.result is not null
group by matches.match_key
having count(team_matches.match_key) != 2
