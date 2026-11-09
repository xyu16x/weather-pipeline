-- 型・名前の整形のみ。ビジネスロジックは marts 側に置く。
select
    lower(trim(location))       as location_alias,
    observed_at,
    cast(observed_at as date)   as observed_date,
    temperature_2m              as temperature_c,
    precipitation               as precipitation_mm,
    wind_speed_10m              as wind_speed_kmh
from {{ source('raw', 'weather_hourly') }}
