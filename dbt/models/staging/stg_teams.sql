select
    id as team_id,
    name,
    short_name,
    aliases,
    country,
    colors.primary as color_primary,
    colors.secondary as color_secondary
from {{ source('raw', 'teams') }}
