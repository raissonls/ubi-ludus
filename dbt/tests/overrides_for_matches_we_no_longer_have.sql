{{ config(severity='warn') }}
-- An override whose match is not in this run's matches does nothing: the match has been played
-- and left the window, or the provider changed its id. It is harmless, so this only warns, and
-- the owner removes the override. Lists each such override once.
select distinct
    o.override_number,
    o.match_id
from {{ ref('stg_overrides') }} as o
left join {{ ref('int_matches_merged') }} as m
    on o.match_id = m.match_id
where m.match_id is null
