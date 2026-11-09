select
    customer_id,
    customer_name,
    {{ normalize_market_code('market_code') }} as market_code,
    upper(trim(segment_code))                  as segment_code,
    cast(onboarded_date as date)               as onboarded_date
from {{ source('raw', 'customers') }}
