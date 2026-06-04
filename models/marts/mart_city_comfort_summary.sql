-- City Comfort Index. Grain: one row per city (aggregated over the loaded period).
with city_days as (
    select * from {{ ref('fct_city_weather_day') }}
),

summary as (
    select
        location_id,
        count(*) as total_days,
        round(avg(temp_mean_c), 1) as avg_temp_c,
        sum(case when is_comfortable then 1 else 0 end) as comfortable_days,
        sum(case when is_rainy then 1 else 0 end) as rainy_days,
        sum(case when is_windy then 1 else 0 end) as windy_days,
        sum(case when is_hot then 1 else 0 end) as hot_days,
        round(avg(avg_european_aqi), 1) as avg_aqi,
        -- Comfort Index = average daily comfort score over the period (0-100).
        round(avg(comfort_score), 1) as comfort_score
    from city_days
    group by location_id
)

select
    summary.location_id,
    dim_location.city_name,
    dim_location.country,
    summary.total_days,
    summary.avg_temp_c,
    summary.comfortable_days,
    summary.rainy_days,
    summary.windy_days,
    summary.hot_days,
    summary.avg_aqi,
    summary.comfort_score
from summary
left join {{ ref('dim_location') }} as dim_location
    on summary.location_id = dim_location.location_id
