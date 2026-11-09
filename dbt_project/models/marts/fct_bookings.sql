-- Grain: one row per booking (after deduplication and cleaning).
select
    booking_id,
    booking_ts,
    booking_date,
    booking_month,
    checkin_date,
    nights,
    lead_time_days,
    market_code,
    segment_code,
    supplier_tier_code,
    customer_id,
    is_cancelled,
    cancelled_at,
    ttv_eur,
    revenue_eur,
    net_ttv_eur,
    net_revenue_eur
from {{ ref('int_bookings_enriched') }}
