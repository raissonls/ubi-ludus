-- Adds the "rescheduled" flag (FR-05) by comparing with the previously published matches.json.
--
-- A kickoff that differs from the previous run's stamps the match with this run's time. The
-- stamp is carried forward from file to file, and the flag lasts reschedule_flag_hours after it.
-- Only a match that is still `scheduled` shows as rescheduled: postponed, cancelled, live and
-- finished keep their own status. A match that was not in the previous file (new, or moved in
-- from beyond the window) has nothing to compare with and is never flagged.
with compared as (
    select
        m.*,
        case
            when p.kickoff_utc is not null and p.kickoff_utc <> m.kickoff_utc
                then cast('{{ var("run_at") }}' as timestamptz)
            else p.rescheduled_at
        end as rescheduled_stamp
    from {{ ref('int_matches_merged') }} as m
    left join {{ ref('stg_previous_matches') }} as p
        on m.match_id = p.match_id
),

flagged as (
    select
        *,
        (
            status = 'scheduled'
            and rescheduled_stamp is not null
            and cast('{{ var("run_at") }}' as timestamptz)
                < rescheduled_stamp + to_hours({{ var('reschedule_flag_hours') }})
        ) as is_rescheduled
    from compared
)

select
    * exclude (status, rescheduled_stamp, is_rescheduled),
    case when is_rescheduled then 'rescheduled' else status end as status,
    case when is_rescheduled then rescheduled_stamp end as rescheduled_at
from flagged
