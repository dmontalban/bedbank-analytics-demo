select
    upper(trim(segment_code)) as segment_code,
    segment_name
from {{ source('raw', 'segments') }}
