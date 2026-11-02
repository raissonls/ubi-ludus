-- Every name of every team, reduced by name_key(), so provider team names can be matched.
-- Names that differ only by accents or punctuation collapse to one key for the same team.
select distinct
    team_id,
    {{ name_key('alias') }} as name_key
from {{ ref('stg_team_aliases') }}
where {{ name_key('alias') }} is not null
