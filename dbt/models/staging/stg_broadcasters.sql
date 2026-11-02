select
    id as broadcaster_id,
    name,
    kind,
    service_id,
    url
from {{ source('raw', 'broadcasters') }}
