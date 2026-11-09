select segment_code, segment_name from {{ ref('stg_segments') }}
