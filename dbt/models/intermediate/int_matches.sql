-- Normalised matches with our team ids and the local calendar date.
-- Times stay in UTC. The local date uses the IANA zone, so any daylight saving rule applies.
select
    m.match_id,
    m.competition_id,
    m.season,
    m.round,
    m.kickoff_utc,
    cast(m.kickoff_utc at time zone '{{ var("display_timezone") }}' as date) as kickoff_local_date,
    strftime(m.kickoff_utc at time zone '{{ var("display_timezone") }}', '%H:%M') as kickoff_local_time,
    home.team_id as home_team_id,
    away.team_id as away_team_id,
    m.status,
    (
        home.resolution in ('mapped', 'undecided')
        and away.resolution in ('mapped', 'undecided')
    ) as teams_resolved
from {{ ref('int_matches_normalised') }} as m
inner join {{ ref('int_match_sides') }} as home
    on m.match_id = home.match_id and home.side = 'home'
inner join {{ ref('int_match_sides') }} as away
    on m.match_id = away.match_id and away.side = 'away'
