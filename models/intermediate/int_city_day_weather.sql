-- One row per city per day: weather actuals + comfort flags + daily air quality,
-- plus a weighted daily comfort score (0-100). This is the analytical base for
-- the fct/mart layer.
with weather as (
    select * from {{ ref('int_weather_flags') }}
),

air_quality as (
    select * from {{ ref('int_air_quality_daily') }}
),

joined as (
    select
        weather.location_id,
        weather.weather_date,
        weather.temp_mean_c,
        weather.temp_max_c,
        weather.temp_min_c,
        weather.precipitation_mm,
        weather.wind_speed_max_kmh,
        weather.is_comfortable,
        weather.is_rainy,
        weather.is_hot,
        weather.is_windy,
        air_quality.avg_european_aqi,
        air_quality.max_european_aqi,
        air_quality.avg_pm2_5
    from weather
    left join air_quality
        on weather.location_id = air_quality.location_id
        and weather.weather_date = air_quality.weather_date
),

scored as (
    select
        *,
        -- Each sub-score is 0-100, higher = more comfortable.
        -- Temperature: best near 22 C (loses 5 pts per degree the mean is away),
        -- plus a heat penalty of 3 pts for every degree the daily max exceeds 30 C,
        -- so hot afternoons reduce comfort even when the mean looks mild.
        greatest(
            0,
            100 - 5 * abs(temp_mean_c - 22) - greatest(0, 3 * (temp_max_c - 30))
        ) as temp_score,
        -- Precipitation: dry is best, loses 10 points per mm (0 by ~10mm).
        greatest(0, 100 - 10 * precipitation_mm) as precip_score,
        -- Wind: calm is best, only penalised above 15 km/h.
        greatest(0, 100 - 3 * greatest(0, wind_speed_max_kmh - 15)) as wind_score,
        -- Air quality: European AQI directly, lower is better (null when no data).
        greatest(0, 100 - avg_european_aqi) as aqi_score
    from joined
)

select
    *,
    -- Weighted daily comfort score (0-100): temp 40%, precip 25%, aqi 20%, wind 15%.
    -- If air quality is missing for the day, renormalise the other weights so the
    -- day still gets a fair score instead of being penalised.
    round(
        case
            when aqi_score is not null
                then 0.40 * temp_score + 0.25 * precip_score + 0.20 * aqi_score + 0.15 * wind_score
            else (0.40 * temp_score + 0.25 * precip_score + 0.15 * wind_score) / 0.80
        end,
        1
    ) as comfort_score
from scored
