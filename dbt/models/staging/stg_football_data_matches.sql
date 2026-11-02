-- football-data.org matches in the internal shape. Only renaming, typing and translating
-- this provider's codes happen here; matching teams and local dates come in the next layer.
with responses as (
    select competition_id, fetched_at, payload
    from {{ source('raw', 'provider_responses') }}
    where provider = 'football-data'
      and resource like 'competitions/%/matches'
),

matches as (
    select
        competition_id,
        fetched_at,
        unnest(from_json(payload -> 'matches', '["json"]')) as m
    from responses
),

typed as (
    select
        competition_id,
        fetched_at,
        json_extract_string(m, '$.id') as provider_match_id,
        cast(json_extract_string(m, '$.utcDate') as timestamptz) as kickoff_utc,
        json_extract_string(m, '$.status') as provider_status,
        json_extract_string(m, '$.stage') as stage,
        cast(json_extract_string(m, '$.matchday') as integer) as matchday,
        cast(json_extract_string(m, '$.season.startDate') as date) as season_start,
        cast(json_extract_string(m, '$.season.endDate') as date) as season_end,
        cast(json_extract_string(m, '$.lastUpdated') as timestamptz) as provider_updated_at,
        json_extract_string(m, '$.homeTeam.name') as home_team_name,
        json_extract_string(m, '$.homeTeam.shortName') as home_team_short_name,
        json_extract_string(m, '$.awayTeam.name') as away_team_name,
        json_extract_string(m, '$.awayTeam.shortName') as away_team_short_name
    from matches
),

latest as (
    -- The same match can arrive in more than one response. Keep the freshest copy.
    select *
    from typed
    qualify row_number() over (
        partition by provider_match_id
        order by provider_updated_at desc nulls last, fetched_at desc
    ) = 1
)

select
    'football-data-' || provider_match_id as match_id,
    competition_id,
    -- Calendar-year seasons (Brazil) read "2026"; seasons that cross a year read "2026-27".
    case
        when year(season_start) = year(season_end) then cast(year(season_start) as varchar)
        else cast(year(season_start) as varchar) || '-'
            || lpad(cast(year(season_end) % 100 as varchar), 2, '0')
    end as season,
    -- League-style rounds are the matchday ("34"). Knockout rounds are the stage ("final").
    case
        when stage in ('REGULAR_SEASON', 'GROUP_STAGE', 'LEAGUE_STAGE') and matchday is not null
            then cast(matchday as varchar)
        when stage is not null then lower(replace(stage, '_', '-'))
    end as round,
    kickoff_utc,
    case provider_status
        when 'SCHEDULED' then 'scheduled'
        when 'TIMED' then 'scheduled'
        when 'IN_PLAY' then 'live'
        when 'PAUSED' then 'live'
        when 'FINISHED' then 'finished'
        when 'AWARDED' then 'finished'
        when 'POSTPONED' then 'postponed'
        when 'SUSPENDED' then 'postponed'
        when 'CANCELLED' then 'cancelled'
    end as status,
    provider_status,
    home_team_name,
    home_team_short_name,
    away_team_name,
    away_team_short_name,
    provider_updated_at
from latest
