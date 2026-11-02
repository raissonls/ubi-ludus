-- The broadcasters of each match after the owner's overrides (FR-11) are applied to what the
-- rights table gives (int_rule_broadcasts). Overrides win over rules.
--
-- The overrides of one match are applied one after the other, oldest `added_at` first and, on the
-- same day, in the order they are written in overrides.yml. The last word wins:
--   add      these broadcasters carry the match too
--   replace  only these carry it: everything before is wiped
--   remove   these do not carry it
-- So a replace followed by an add keeps both, an add followed by a replace keeps only the
-- replace, and a remove followed by an add of the same broadcaster puts it back.
--
-- How sure we are: a broadcaster the owner put there (listed by the last replace, or added after
-- it) is `confirmed`, source `override`. One that only the rights table gives stays `rule`. If
-- overrides leave a match with no broadcaster at all, it is unknown again: see int_broadcasts.
with ordered as (
    select
        *,
        dense_rank() over (partition by match_id order by added_at, override_number) as step
    from {{ ref('stg_overrides') }}
),

last_replace as (
    select match_id, max(step) as step
    from ordered
    where action = 'replace'
    group by match_id
),

candidates as (
    select match_id, broadcaster_id from {{ ref('int_rule_broadcasts') }}
    union
    select match_id, broadcaster_id from ordered
),

decided as (
    select
        c.match_id,
        c.broadcaster_id,
        lr.step as replace_step,
        exists (
            select 1 from {{ ref('int_rule_broadcasts') }} as r
            where r.match_id = c.match_id and r.broadcaster_id = c.broadcaster_id
        ) as in_rules,
        exists (
            select 1 from ordered as o
            where o.match_id = c.match_id
                and o.broadcaster_id = c.broadcaster_id
                and o.action = 'replace'
                and o.step = lr.step
        ) as in_last_replace,
        -- The last add or remove that came after the last replace (or at all, with no replace).
        (
            select arg_max(o.action, o.step)
            from ordered as o
            where o.match_id = c.match_id
                and o.broadcaster_id = c.broadcaster_id
                and o.action in ('add', 'remove')
                and o.step > coalesce(lr.step, 0)
        ) as last_action
    from candidates as c
    left join last_replace as lr on c.match_id = lr.match_id
),

resolved as (
    select
        *,
        case last_action
            when 'add' then true
            when 'remove' then false
            else case when replace_step is not null then in_last_replace else in_rules end
        end as carries,
        (replace_step is not null or last_action = 'add') as put_there_by_owner
    from decided
)

select
    match_id,
    broadcaster_id,
    case when put_there_by_owner then 'confirmed' else 'rule' end as confidence,
    case when put_there_by_owner then 'override' else 'rights_rule' end as source
from resolved
where carries
