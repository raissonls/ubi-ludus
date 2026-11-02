-- One row per real-world match when two providers both know it (FR-01, "merge, don't duplicate").
--
-- The same match is a row from each provider with different ids. They are the same match when,
-- inside one competition, our team ids and their order (home, away) are equal and the kickoffs
-- are less than a day apart. The wider-than-zero margin absorbs a provider that is slow to
-- follow a reschedule; a day is short enough that two legs of one tie never merge.
--
-- Only the copy of the lowest-ranked provider is kept, so its id, status and kickoff are the
-- ones published. A match with an undecided team has no id to compare and stays as it is.
select m.*
from {{ ref('int_matches') }} as m
where not exists (
    select 1
    from {{ ref('int_matches') }} as better
    where better.competition_id = m.competition_id
      and better.home_team_id = m.home_team_id
      and better.away_team_id = m.away_team_id
      and better.provider_rank < m.provider_rank
      and abs(date_diff('second', better.kickoff_utc, m.kickoff_utc)) < 86400
)
