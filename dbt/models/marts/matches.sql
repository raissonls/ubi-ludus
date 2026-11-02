-- Shaped like one record of matches.json (schemas/match.schema.json). Left out of this table:
--   * matches whose teams are unmapped (reported by the unmapped_teams_are_reported test)
--   * matches outside their competition's window: yesterday through `horizon_days` ahead,
--     counted in Brazil's calendar (FR-04)
with broadcasts as (
    -- A list of broadcast records per match; a match nothing is known about has one "unknown".
    select
        match_id,
        list(
            {
                'broadcaster_id': broadcaster_id,
                'confidence': confidence,
                'source': source,
                'updated_at': strftime(updated_at at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ')
            }
            order by broadcaster_id nulls last
        ) as broadcasts
    from {{ ref('int_broadcasts') }}
    group by match_id
)

select
    m.match_id as id,
    m.competition_id,
    m.season,
    m.round,
    strftime(m.kickoff_utc at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ') as kickoff_utc,
    m.home_team_id,
    m.away_team_id,
    m.status,
    b.broadcasts,
    strftime(m.rescheduled_at at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ') as rescheduled_at
from {{ ref('int_matches_flagged') }} as m
inner join {{ ref('stg_competitions') }} as c
    on m.competition_id = c.competition_id
left join broadcasts as b
    on m.match_id = b.match_id
where m.teams_resolved
    and m.kickoff_local_date >= cast('{{ var("today") }}' as date) - 1
    and m.kickoff_local_date <= cast('{{ var("today") }}' as date) + c.horizon_days
order by m.kickoff_utc, m.match_id
