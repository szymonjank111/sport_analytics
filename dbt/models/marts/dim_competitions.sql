select
    competition_id,
    name,
    country,
    tier,
    competition_type,
    season_calendar,
    has_xg,
    has_match_stats,
    has_odds
from {{ ref('competitions') }}
