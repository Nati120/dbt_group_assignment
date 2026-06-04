-- Derive per city-day comfort flags from the daily weather actuals.
-- Thresholds are the team's definition of "comfortable" — adjust together if needed.
with daily as (
    select * from {{ ref('stg_weather_daily') }}
)

select
    location_id,
    weather_date,
    temp_mean_c,
    temp_max_c,
    temp_min_c,
    precipitation_mm,
    wind_speed_max_kmh,
    (
        temp_mean_c between 18 and 26
        and precipitation_mm < 1
        and wind_speed_max_kmh < 25
    ) as is_comfortable,
    precipitation_mm >= 1 as is_rainy,
    temp_max_c >= 32 as is_hot,
    wind_speed_max_kmh >= 25 as is_windy
from daily
