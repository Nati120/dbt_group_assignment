-- Fact table. Grain: one row per city per day.
select
    {{ dbt_utils.generate_surrogate_key(['location_id', 'weather_date']) }} as city_weather_day_id,
    location_id,
    weather_date,
    temp_mean_c,
    temp_max_c,
    temp_min_c,
    precipitation_mm,
    wind_speed_max_kmh,
    avg_european_aqi,
    max_european_aqi,
    avg_pm2_5,
    is_comfortable,
    is_rainy,
    is_hot,
    is_windy,
    temp_score,
    precip_score,
    wind_score,
    aqi_score,
    comfort_score
from {{ ref('int_city_day_weather') }}
