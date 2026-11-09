-- 日本の観測値として非現実的な気温を弾く
select *
from {{ ref('stg_weather_hourly') }}
where temperature_c is not null
  and (temperature_c < -50 or temperature_c > 50)
