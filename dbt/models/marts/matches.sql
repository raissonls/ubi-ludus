-- Shaped like one record of matches.json (schemas/match.schema.json), without `broadcasts`,
-- which the rights engine adds (M2). Left out of this table:
--   * matches whose teams are unmapped (reported by the unmapped_teams_are_reported test)
--   * matches outside their competition's window: yesterday through `horizon_days` ahead,
--     counted in Brazil's calendar (FR-04)
select
    m.match_id as id,
    m.competition_id,
    m.season,
    m.round,
    strftime(m.kickoff_utc at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ') as kickoff_utc,
    m.home_team_id,
    m.away_team_id,
    m.status,
    strftime(m.rescheduled_at at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ') as rescheduled_at
from {{ ref('int_matches_flagged') }} as m
inner join {{ ref('stg_competitions') }} as c
    on m.competition_id = c.competition_id
where m.teams_resolved
    and m.kickoff_local_date >= cast('{{ var("today") }}' as date) - 1
    and m.kickoff_local_date <= cast('{{ var("today") }}' as date) + c.horizon_days
order by m.kickoff_utc, m.match_id
