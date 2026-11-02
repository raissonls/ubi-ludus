-- Provider team names we could not tie to exactly one of our teams. The matches that carry
-- them are held back from the published file until someone adds the name as an alias.
select
    side.team_name,
    side.team_short_name,
    side.resolution,
    count(*) as match_count,
    min(m.competition_id) as example_competition_id
from {{ ref('int_match_sides') }} as side
inner join {{ ref('int_matches_normalised') }} as m
    on side.match_id = m.match_id
where side.resolution in ('unmapped', 'ambiguous')
group by side.team_name, side.team_short_name, side.resolution
