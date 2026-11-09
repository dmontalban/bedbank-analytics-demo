{#
  The analytical cube that feeds the dashboard.
  Grain: month x market x segment x supplier tier (34 x 8 x 4 x 3 = 3,264 cells).
  "gross" = every booking made; "net" = bookings that were not cancelled.
  take rate = net revenue / net TTV;  ABV = net TTV / net bookings.
#}
select
    booking_month                                                  as month_start,
    market_code,
    segment_code,
    supplier_tier_code,
    count(*)                                                       as gross_bookings,
    count(*) filter (where not is_cancelled)                       as net_bookings,
    cast(sum(ttv_eur) as double)                                   as gross_ttv_eur,
    cast(sum(net_ttv_eur) as double)                               as net_ttv_eur,
    cast(sum(revenue_eur) as double)                               as gross_revenue_eur,
    cast(sum(net_revenue_eur) as double)                           as net_revenue_eur
from {{ ref('fct_bookings') }}
group by 1, 2, 3, 4
