-- A match is `rescheduled` exactly when it has a rescheduled_at, and never the other way round.
select id, status, rescheduled_at
from {{ ref('matches') }}
where (status = 'rescheduled') <> (rescheduled_at is not null)
