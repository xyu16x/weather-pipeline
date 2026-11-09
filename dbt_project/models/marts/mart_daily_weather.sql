-- 地点×日の集計。地点名は seed の alias で名寄せする。
select
    a.location_id,
    a.location_name_ja,
    s.observed_date,
    count(s.temperature_c)       as temperature_obs_count,  -- 欠損を除いた観測数
    min(s.temperature_c)         as temp_min_c,
    max(s.temperature_c)         as temp_max_c,
    round(avg(s.temperature_c), 2) as temp_avg_c,
    sum(s.precipitation_mm)      as precipitation_total_mm,
    max(s.wind_speed_kmh)        as wind_speed_max_kmh
from {{ ref('stg_weather_hourly') }} s
inner join {{ ref('location_aliases') }} a
    on s.location_alias = a.alias
group by 1, 2, 3
