-- Roll the hourly air quality observations up to one row per city per day.
with hourly as (
    select * from {{ ref('stg_air_quality_hourly') }}
)

select
    location_id,
    observed_date as weather_date,
    avg(european_aqi) as avg_european_aqi,
    max(european_aqi) as max_european_aqi,
    avg(pm2_5) as avg_pm2_5,
    avg(pm10) as avg_pm10
from hourly
group by location_id, observed_date
