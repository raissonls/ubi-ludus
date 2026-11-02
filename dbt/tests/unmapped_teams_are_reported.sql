{{ config(severity='warn') }}

-- Warns, and does not fail, when a provider team has no match in our team list. Those matches
-- are left out of matches.json; the fix is to add the provider's spelling as an alias.
select * from {{ ref('int_unmapped_teams') }}
