select supplier_tier_code, supplier_tier_name from {{ ref('stg_supplier_tiers') }}
