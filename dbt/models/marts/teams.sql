-- Shaped like one record of teams.json (schemas/team.schema.json).
select
    team_id as id,
    name,
    short_name,
    aliases,
    country,
    {'primary': color_primary, 'secondary': color_secondary} as colors
from {{ ref('stg_teams') }}
order by team_id
