-- A team without a mapping would silently drop its matches from the marts.
select
    source,
    team_key,
    team_name
from {{ ref('int_unmapped_teams') }}
