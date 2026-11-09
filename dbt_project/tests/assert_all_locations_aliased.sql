-- seed に未登録の地点名があれば失敗(名寄せ漏れ検知)
select distinct s.location_alias
from {{ ref('stg_weather_hourly') }} s
left join {{ ref('location_aliases') }} a on s.location_alias = a.alias
where a.alias is null
