-- Forecast fact table. Grain: one row per city per forecast date (latest extraction run).
-- Includes an estimated comfort score calculated without AQI (not available in forecast data).
-- Weights are renormalised: temperature 50%, precipitation 30%, wind 20%.
with forecast as (
    select * from {{ ref('stg_forecast_daily') }}
),

-- Keep only the most recent extraction run per city-day
latest as (
    select
        location_id,
        forecast_date,
        max(forecast_run_at) as forecast_run_at
    from forecast
    group by location_id, forecast_date
),

deduped as (
    select f.*
    from forecast as f
    inner join latest using (location_id, forecast_date, forecast_run_at)
),

scored as (
    select
        {{ dbt_utils.generate_surrogate_key(['location_id', 'forecast_date']) }} as forecast_day_id,
        location_id,
        forecast_date,
        forecast_run_at,
        temp_max_c,
        temp_min_c,
        temp_mean_c,
        precipitation_mm,
        rain_mm,
        snowfall_cm,
        wind_speed_max_kmh,

        -- Temperature sub-score: peaks at 22C, heat penalty above 30C max
        greatest(
            least(100 - abs(temp_mean_c - 22) * 5, 100),
            0
        ) - greatest(least((temp_max_c - 30) * 3, 100), 0) as temp_score_raw,

        -- Precipitation sub-score
        greatest(100 - precipitation_mm * 10, 0) as precip_score,

        -- Wind sub-score
        greatest(100 - greatest(wind_speed_max_kmh - 15, 0) * 3, 0) as wind_score
    from deduped
)

select
    forecast_day_id,
    location_id,
    forecast_date,
    forecast_run_at,
    temp_max_c,
    temp_min_c,
    temp_mean_c,
    precipitation_mm,
    rain_mm,
    snowfall_cm,
    wind_speed_max_kmh,
    greatest(temp_score_raw, 0) as temp_score,
    precip_score,
    wind_score,
    round(
        greatest(temp_score_raw, 0) * 0.50
        + precip_score * 0.30
        + wind_score * 0.20,
        1
    ) as comfort_score_est
from scored
