select
    competition_id,
    name,
    country,
    tier,
    season_calendar,
    has_xg,
    has_match_stats,
    has_odds
from {{ ref('competitions') }}
