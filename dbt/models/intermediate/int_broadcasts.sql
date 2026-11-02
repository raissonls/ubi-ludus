-- One row per match and broadcaster, with how sure we are (FR-12), and a single "unknown" row
-- for a match nothing is known about (FR-13). An unknown row never names a broadcaster.
--   confirmed : the owner checked this match (an override)
--   rule      : from the rights table
--   unknown   : nothing is known, so nothing is guessed. Also what a match becomes when overrides
--               remove every broadcaster it had.
-- (Provider data could also confirm a broadcast, but no provider we use gives broadcasters.)
with known as (
    -- Only matches we have: an override for one that is gone changes nothing.
    select
        r.match_id,
        r.broadcaster_id,
        r.confidence,
        r.source
    from {{ ref('int_resolved_broadcasts') }} as r
    inner join {{ ref('int_matches_merged') }} as m
        on r.match_id = m.match_id
),

unknown as (
    select
        m.match_id,
        cast(null as varchar) as broadcaster_id,
        'unknown' as confidence,
        'none' as source
    from {{ ref('int_matches_merged') }} as m
    where not exists (select 1 from known as k where k.match_id = m.match_id)
),

all_rows as (
    select * from known
    union all
    select * from unknown
)

select
    *,
    cast('{{ var("run_at") }}' as timestamptz) as updated_at
from all_rows
