-- One row per match and broadcaster, with how sure we are (FR-12), and a single "unknown" row
-- for a match nothing is known about (FR-13). An unknown row never names a broadcaster.
--   rule     : from the rights table
--   unknown  : nothing is known, so nothing is guessed
-- (`confirmed` comes from overrides, M2-03, and from provider data, which no provider gives us.)
with known as (
    select
        match_id,
        broadcaster_id,
        'rule' as confidence,
        'rights_rule' as source
    from {{ ref('int_rule_broadcasts') }}
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
