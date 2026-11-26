select
    d.location_id,
    d.location_name_ja,
    cast(date_trunc('month', d.observed_date) as date) as observed_month,
    round(max(d.temp_max_c), 2) as temp_max_c,
    round(min(d.temp_min_c), 2) as temp_min_c,
    round(sum(d.precipitation_total_mm), 1) as precipitation_total_mm,
    count(d.location_name_ja) as day_count,
from {{ ref('mart_daily_weather') }} d
group by 1, 2, 3