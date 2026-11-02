-- Shaped like one record of competitions.json (schemas/competition.schema.json).
select
    competition_id as id,
    name,
    country_or_region,
    type,
    map_from_entries(
        list_transform(sources, lambda s: {'k': s.provider, 'v': s.provider_id})
    ) as provider_ids,
    coverage
from {{ ref('stg_competitions') }}
order by competition_id
