-- FR-13: a match nothing is known about never shows a broadcaster, and a broadcast that names a
-- broadcaster always says how sure we are. Returns the rows that break either rule, or a match
-- that is both "unknown" and given a broadcaster.
select match_id, broadcaster_id, confidence
from {{ ref('int_broadcasts') }}
where (confidence = 'unknown' and broadcaster_id is not null)
    or (confidence <> 'unknown' and broadcaster_id is null)

union all

select match_id, null as broadcaster_id, 'unknown next to a broadcaster' as confidence
from {{ ref('int_broadcasts') }}
group by match_id
having count(*) filter (where confidence = 'unknown') > 0
    and count(*) filter (where confidence <> 'unknown') > 0
