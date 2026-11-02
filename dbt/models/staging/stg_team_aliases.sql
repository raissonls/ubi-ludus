-- Every name a team can be called: its full name, short name and listed aliases.
-- Used later to match the same club across providers (M1-04).
with names as (
    select team_id, name as alias from {{ ref('stg_teams') }}
    union
    select team_id, short_name as alias from {{ ref('stg_teams') }}
    union
    select team_id, unnest(aliases) as alias from {{ ref('stg_teams') }}
)

select distinct team_id, alias from names
