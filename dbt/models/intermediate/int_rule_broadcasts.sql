-- The broadcasters the rights table gives to each match (FR-10).
--
-- A rule covers a match when all of these hold:
--   * same competition and same season;
--   * the match's local date (Brazil) is inside valid_from..valid_to, both included;
--   * its scope fits: `all` fits every match; `round` and `stage` fit when the match's round
--     is the scope value (a matchday such as 33, or a knockout stage such as final); `team` fits
--     when either team is that team.
--
-- Rights add up. Every rule that covers a match contributes its broadcasters, and a broadcaster
-- named by several rules is listed once. A rule never takes another's broadcasters away: to say
-- "only on X for this match", write an override (M2-03).
select distinct
    m.match_id,
    r.broadcaster_id
from {{ ref('int_matches_merged') }} as m
inner join {{ ref('stg_rights_rule_broadcasters') }} as r
    on m.competition_id = r.competition_id
    and m.season = r.season
    and m.kickoff_local_date between r.valid_from and r.valid_to
    and case r.scope
        when 'all' then true
        when 'round' then m.round = r.scope_value
        when 'stage' then m.round = r.scope_value
        when 'team' then r.scope_value in (m.home_team_id, m.away_team_id)
        else false
    end
