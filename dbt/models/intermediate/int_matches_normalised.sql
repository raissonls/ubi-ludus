-- Matches from every provider in one shape. A new provider adds a staging model and a line here.
select * from {{ ref('stg_football_data_matches') }}
