select market_code, market_name, region from {{ ref('stg_markets') }}
