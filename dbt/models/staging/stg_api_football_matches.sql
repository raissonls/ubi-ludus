-- API-Football fixtures in the internal shape. Only renaming, typing and translating this
-- provider's codes happen here; matching teams and local dates come in the next layer.
-- A response holds the fixtures of one day across leagues, so the competition is found by
-- league id in config/competitions.yml. A league we do not follow is dropped.
with responses as (
    select fetched_at, payload
    from {{ source('raw', 'provider_responses') }}
    where provider = 'api-football'
      and resource = 'fixtures'
),

fixtures as (
    select
        fetched_at,
        unnest(from_json(payload -> 'response', '["json"]')) as f
    from responses
),

leagues as (
    select
        competition_id,
        cast(s.provider_id as varchar) as league_id
    from (select competition_id, unnest(sources) as s from {{ ref('stg_competitions') }})
    where s.provider = 'api-football'
),

typed as (
    select
        fetched_at,
        json_extract_string(f, '$.fixture.id') as provider_match_id,
        json_extract_string(f, '$.league.id') as league_id,
        cast(json_extract_string(f, '$.league.season') as integer) as season_year,
        json_extract_string(f, '$.league.round') as round_label,
        cast(json_extract_string(f, '$.fixture.date') as timestamptz) as kickoff_utc,
        json_extract_string(f, '$.fixture.status.short') as provider_status,
        json_extract_string(f, '$.teams.home.name') as home_team_name,
        json_extract_string(f, '$.teams.away.name') as away_team_name
    from fixtures
),

latest as (
    -- The same fixture can arrive in more than one response. Keep the freshest copy.
    select *
    from typed
    qualify row_number() over (
        partition by provider_match_id
        order by fetched_at desc
    ) = 1
)

select
    'api-football-' || l.provider_match_id as match_id,
    leagues.competition_id,
    -- The provider's season is the year it starts in. Every competition served only by this
    -- provider runs inside a calendar year, which is how seasons read in Brazil ("2026").
    cast(l.season_year as varchar) as season,
    -- "Regular Season - 33" is round 33. Knockout labels become slugs ("quarter-finals").
    case
        when regexp_matches(l.round_label, ' - [0-9]+$') then regexp_extract(l.round_label, '([0-9]+)$', 1)
        when l.round_label is not null then trim(regexp_replace(lower(l.round_label), '[^a-z0-9]+', '-', 'g'), '-')
    end as round,
    l.kickoff_utc,
    case l.provider_status
        when 'NS' then 'scheduled'
        when '1H' then 'live'
        when 'HT' then 'live'
        when '2H' then 'live'
        when 'ET' then 'live'
        when 'BT' then 'live'
        when 'P' then 'live'
        when 'LIVE' then 'live'
        when 'INT' then 'live'
        when 'FT' then 'finished'
        when 'AET' then 'finished'
        when 'PEN' then 'finished'
        when 'AWD' then 'finished'
        when 'WO' then 'finished'
        when 'PST' then 'postponed'
        when 'SUSP' then 'postponed'
        when 'ABD' then 'postponed'
        when 'CANC' then 'cancelled'
    end as status,
    l.provider_status,
    l.home_team_name,
    cast(null as varchar) as home_team_short_name,
    l.away_team_name,
    cast(null as varchar) as away_team_short_name,
    cast(null as timestamptz) as provider_updated_at
from latest as l
inner join leagues
    on l.league_id = leagues.league_id
-- TBD: the day is known but not the time. A made-up midnight kickoff would mislead, so the
-- fixture waits until the provider has a time.
where l.provider_status <> 'TBD'
