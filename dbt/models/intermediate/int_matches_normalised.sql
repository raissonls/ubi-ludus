-- Matches from every provider in one shape. A new provider adds a staging model and a part here.
-- provider_rank says whose copy wins when two providers know the same match (lower wins):
-- football-data.org first, because its window is longer and its rows carry `lastUpdated`.
select 1 as provider_rank, 'football-data' as provider, * from {{ ref('stg_football_data_matches') }}
union all by name
select 2 as provider_rank, 'api-football' as provider, * from {{ ref('stg_api_football_matches') }}
