-- Shaped like one record of matches.json (schemas/match.schema.json), without `broadcasts`,
-- which the rights engine adds (M2). Matches whose teams are unmapped are held back.
select
    match_id as id,
    competition_id,
    season,
    round,
    strftime(kickoff_utc at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ') as kickoff_utc,
    home_team_id,
    away_team_id,
    status
from {{ ref('int_matches') }}
where teams_resolved
order by kickoff_utc, match_id
