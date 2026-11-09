{#
  Derived fields every downstream model needs:
  lead time, and the "net" amounts (what survives cancellations).
#}
select
    b.booking_id,
    b.booking_ts,
    b.booking_date,
    b.booking_month,
    b.checkin_date,
    b.nights,
    date_diff('day', b.booking_date, b.checkin_date)        as lead_time_days,
    b.market_code,
    b.segment_code,
    b.supplier_tier_code,
    b.customer_id,
    b.is_cancelled,
    b.cancelled_at,
    b.ttv_eur,
    b.revenue_eur,
    case when b.is_cancelled then 0 else b.ttv_eur end      as net_ttv_eur,
    case when b.is_cancelled then 0 else b.revenue_eur end  as net_revenue_eur
from {{ ref('stg_bookings') }} as b
