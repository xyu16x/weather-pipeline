-- 地点×月が重複していたら失敗(行が返る=失敗)
select location_id, observed_month, count(*) as n
from {{ ref('mart_monthly_weather') }}
group by 1, 2
having count(*) > 1
