select
    location_id,
    city_name,
    country,
    country_code,
    admin1 as region,
    cast(latitude as double) as latitude,
    cast(longitude as double) as longitude,
    timezone,
    cast(elevation as double) as elevation_m,
    cast(population as bigint) as population,
    cast(extracted_at as timestamp) as extracted_at
from {{ source('open_meteo', 'raw_locations') }}
