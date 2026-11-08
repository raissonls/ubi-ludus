select
    id as team_id,
    name,
    short_name,
    aliases,
    country,
    colors.primary as color_primary,
    colors.secondary as color_secondary,
    kind,
    shirt.primary as shirt_primary,
    shirt.secondary as shirt_secondary
from {{ source('raw', 'teams') }}
