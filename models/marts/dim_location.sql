-- Conformed city dimension. One row per city.
select
    location_id,
    city_name,
    country,
    country_code,
    region,
    latitude,
    longitude,
    timezone,
    elevation_m,
    population
from {{ ref('stg_locations') }}
