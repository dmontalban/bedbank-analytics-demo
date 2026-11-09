select
    upper(trim(supplier_tier_code)) as supplier_tier_code,
    supplier_tier_name
from {{ source('raw', 'supplier_tiers') }}
