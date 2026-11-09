select
    upper(trim(market_code)) as market_code,
    market_name,
    region
from {{ source('raw', 'markets') }}
