-- A team without a mapping would silently drop its matches from the marts.
select * from {{ ref('int_unmapped_teams') }}
