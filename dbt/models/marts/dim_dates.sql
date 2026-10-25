select
    date_day,
    extract(year from date_day) as year,
    extract(month from date_day) as month,
    cast(format_date('%u', date_day) as int64) as iso_day_of_week,
    format_date('%A', date_day) as day_name,
    -- Unlike %u, dayofweek counts from 1 for Sunday.
    extract(dayofweek from date_day) in (1, 7) as is_weekend
from unnest(generate_date_array(date '2010-01-01', date '2030-12-31')) as date_day
