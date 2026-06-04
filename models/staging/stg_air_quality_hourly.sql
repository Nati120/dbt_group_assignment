select
    location_id,
    -- Open-Meteo returns hourly time as ISO without seconds, e.g. 2026-06-04T00:00
    strptime(timestamp, '%Y-%m-%dT%H:%M') as observed_at,
    cast(strptime(timestamp, '%Y-%m-%dT%H:%M') as date) as observed_date,
    cast(pm10 as double) as pm10,
    cast(pm2_5 as double) as pm2_5,
    cast(carbon_monoxide as double) as carbon_monoxide,
    cast(nitrogen_dioxide as double) as nitrogen_dioxide,
    cast(ozone as double) as ozone,
    cast(european_aqi as double) as european_aqi
from {{ source('open_meteo', 'raw_air_quality_hourly') }}
