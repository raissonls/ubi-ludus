-- FR-12: no match is published without a confidence tag. A match with nothing known carries
-- one "unknown" broadcast, so an empty list means the join or a model upstream is broken.
-- Also a match must not list the same broadcaster twice.
select id
from {{ ref('matches') }}
where broadcasts is null or len(broadcasts) = 0

union all

select match_id as id
from {{ ref('int_broadcasts') }}
where broadcaster_id is not null
group by match_id, broadcaster_id
having count(*) > 1
