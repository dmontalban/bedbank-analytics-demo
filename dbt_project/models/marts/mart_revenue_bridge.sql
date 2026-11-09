{#
  Price-volume-mix-rate bridge: why did net revenue change versus the same months a year earlier?

  Items i = market x segment x supplier tier.   B = net bookings, T = net TTV, R = net revenue
    ABV = T / B        take rate TR = R / T        revenue per booking r = R / B = ABV x TR
    "cur" = current period, "base" = same months a year earlier, Rbar_base = sum(R_base) / sum(B_base)

    volume = (sum B_cur - sum B_base) x Rbar_base
    mix    = sum_i B_cur_i x r_base_i  -  sum B_cur x Rbar_base
    price  = sum_i B_cur_i x (ABV_cur_i - ABV_base_i) x TR_base_i
    rate   = sum_i T_cur_i x (TR_cur_i - TR_base_i)

  The four effects add up exactly to R_cur - R_base (tests/assert_bridge_identity.sql checks it).
#}
with periods as (

    select * from (values
        ('LTM',   date '2025-11-01', date '2026-10-01', date '2024-11-01', date '2025-10-01'),
        ('YTD26', date '2026-01-01', date '2026-10-01', date '2025-01-01', date '2025-10-01'),
        ('FY25',  date '2025-01-01', date '2025-12-01', date '2024-01-01', date '2024-12-01')
    ) as t(period, cur_start, cur_end, base_start, base_end)

),

items as (

    select
        p.period,
        c.market_code,
        c.segment_code,
        c.supplier_tier_code,
        sum(c.net_bookings)    filter (where c.month_start between p.cur_start  and p.cur_end)   as b_cur,
        sum(c.net_ttv_eur)     filter (where c.month_start between p.cur_start  and p.cur_end)   as t_cur,
        sum(c.net_revenue_eur) filter (where c.month_start between p.cur_start  and p.cur_end)   as r_cur,
        sum(c.net_bookings)    filter (where c.month_start between p.base_start and p.base_end)  as b_base,
        sum(c.net_ttv_eur)     filter (where c.month_start between p.base_start and p.base_end)  as t_base,
        sum(c.net_revenue_eur) filter (where c.month_start between p.base_start and p.base_end)  as r_base
    from {{ ref('mart_revenue_cube') }} as c
    cross join periods as p
    group by 1, 2, 3, 4

),

rates as (

    select
        *,
        r_base / nullif(b_base, 0)                      as rev_per_booking_base,
        t_cur  / nullif(b_cur, 0)                       as abv_cur,
        t_base / nullif(b_base, 0)                      as abv_base,
        r_cur  / nullif(t_cur, 0)                       as take_rate_cur,
        r_base / nullif(t_base, 0)                      as take_rate_base
    from items

)

select
    period,
    sum(r_base)                                                                   as revenue_base,
    (sum(b_cur) - sum(b_base)) * (sum(r_base) / sum(b_base))                      as volume_effect,
    sum(b_cur * rev_per_booking_base) - sum(b_cur) * (sum(r_base) / sum(b_base))  as mix_effect,
    sum(b_cur * (abv_cur - abv_base) * take_rate_base)                            as price_effect,
    sum(t_cur * (take_rate_cur - take_rate_base))                                 as rate_effect,
    sum(r_cur)                                                                    as revenue_current,
    (sum(r_cur) - sum(r_base))
      - ( (sum(b_cur) - sum(b_base)) * (sum(r_base) / sum(b_base))
        + sum(b_cur * rev_per_booking_base) - sum(b_cur) * (sum(r_base) / sum(b_base))
        + sum(b_cur * (abv_cur - abv_base) * take_rate_base)
        + sum(t_cur * (take_rate_cur - take_rate_base)) )                         as residual
from rates
group by period
