-- 地点×日が重複していたら失敗(行が返る=失敗)
select location_id, observed_date, count(*) as n
from {{ ref('mart_daily_weather') }}
group by 1, 2
having count(*) > 1
