-- The rights table with one row per rule and broadcaster (a rule lists several).
-- rule_number is the rule's place in rights.yml, so a problem can be traced back to the file.
select
    rule_number,
    competition_id,
    season,
    scope,
    scope_value,
    unnest(broadcasters) as broadcaster_id,
    valid_from,
    valid_to
from {{ source('raw', 'rights_rules') }}
