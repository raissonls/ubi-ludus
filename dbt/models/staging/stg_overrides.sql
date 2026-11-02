-- Match-level overrides with one row per override and broadcaster (an override lists several).
-- override_number is the override's place in overrides.yml. Of two overrides added on the same
-- day, the lower number comes first and the higher one has the last word.
select
    override_number,
    match_id,
    action,
    unnest(broadcasters) as broadcaster_id,
    added_at,
    reason
from {{ source('raw', 'overrides') }}
