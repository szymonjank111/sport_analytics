select
    team_id,
    name,
    country
from {{ ref('teams') }}
