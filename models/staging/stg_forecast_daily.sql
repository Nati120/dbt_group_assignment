select
    location_id,
    cast(date as date) as forecast_date,
    cast(extracted_at as timestamp) as forecast_run_at,
    cast(temperature_2m_max as double) as temp_max_c,
    cast(temperature_2m_min as double) as temp_min_c,
    cast(temperature_2m_mean as double) as temp_mean_c,
    cast(precipitation_sum as double) as precipitation_mm,
    cast(rain_sum as double) as rain_mm,
    cast(snowfall_sum as double) as snowfall_cm,
    cast(wind_speed_10m_max as double) as wind_speed_max_kmh
from {{ source('open_meteo', 'raw_forecast_daily') }}
