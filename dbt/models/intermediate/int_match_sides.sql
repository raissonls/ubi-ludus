-- One row per team slot of a match, with the team it resolves to.
--   undecided : the provider has no team yet (for example a final between two semi-final winners)
--   mapped    : exactly one of our teams carries that name
--   unmapped  : no team of ours carries that name
--   ambiguous : more than one team does
with sides as (
    select
        match_id,
        'home' as side,
        home_team_name as team_name,
        home_team_short_name as team_short_name
    from {{ ref('int_matches_normalised') }}
    union all
    select
        match_id,
        'away' as side,
        away_team_name as team_name,
        away_team_short_name as team_short_name
    from {{ ref('int_matches_normalised') }}
),

keyed as (
    select
        *,
        {{ name_key('team_name') }} as full_key,
        {{ name_key('team_short_name') }} as short_key
    from sides
),

candidates as (
    select
        k.match_id,
        k.side,
        n.team_id
    from keyed as k
    inner join {{ ref('int_team_name_keys') }} as n
        on n.name_key in (k.full_key, k.short_key)
    group by k.match_id, k.side, n.team_id
),

resolved as (
    select
        match_id,
        side,
        count(*) as team_count,
        min(team_id) as team_id
    from candidates
    group by match_id, side
)

select
    k.match_id,
    k.side,
    k.team_name,
    k.team_short_name,
    case
        when k.full_key is null and k.short_key is null then 'undecided'
        when r.team_count = 1 then 'mapped'
        when r.team_count > 1 then 'ambiguous'
        else 'unmapped'
    end as resolution,
    case when r.team_count = 1 then r.team_id end as team_id
from keyed as k
left join resolved as r
    on k.match_id = r.match_id and k.side = r.side
