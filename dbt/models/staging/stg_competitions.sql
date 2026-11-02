select
    id as competition_id,
    name,
    country_or_region,
    type,
    coverage,
    cast(horizon_days as integer) as horizon_days,
    sources
from {{ source('raw', 'competitions') }}
