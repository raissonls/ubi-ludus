-- Matches as published by the previous run, typed. Only used to spot kickoffs that moved.
select
    id as match_id,
    cast(kickoff_utc as timestamptz) as kickoff_utc,
    status,
    cast(rescheduled_at as timestamptz) as rescheduled_at
from {{ source('raw', 'previous_matches') }}
