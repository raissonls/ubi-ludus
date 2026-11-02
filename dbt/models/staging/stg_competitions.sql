select
    id as competition_id,
    name,
    country_or_region,
    type,
    coverage,
    sources
from {{ source('raw', 'competitions') }}
