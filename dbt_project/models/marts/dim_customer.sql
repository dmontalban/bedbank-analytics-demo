select customer_id, customer_name, market_code, segment_code, onboarded_date
from {{ ref('stg_customers') }}
