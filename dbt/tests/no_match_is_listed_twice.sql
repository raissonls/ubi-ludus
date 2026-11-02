{{ config(severity='warn') }}
-- Two matches of one competition with the same teams in the same order and kickoffs less than a
-- day apart are one match listed twice. The merge (int_matches_merged) should leave none; this
-- warns instead of stopping the run, because a duplicate on the site is better than no site.
select
    a.match_id,
    b.match_id as other_match_id
from {{ ref('int_matches_merged') }} as a
inner join {{ ref('int_matches_merged') }} as b
    on a.competition_id = b.competition_id
    and a.home_team_id = b.home_team_id
    and a.away_team_id = b.away_team_id
    and a.match_id < b.match_id
    and abs(date_diff('second', a.kickoff_utc, b.kickoff_utc)) < 86400
