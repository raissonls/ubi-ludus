-- Fails if a published match is outside its competition's window. The mart filters on the same
-- rule, so this guards against someone changing one without the other.
select m.id, m.competition_id, i.kickoff_local_date, c.horizon_days
from {{ ref('matches') }} as m
inner join {{ ref('int_matches') }} as i
    on m.id = i.match_id
inner join {{ ref('stg_competitions') }} as c
    on m.competition_id = c.competition_id
where i.kickoff_local_date < cast('{{ var("today") }}' as date) - 1
    or i.kickoff_local_date > cast('{{ var("today") }}' as date) + c.horizon_days
