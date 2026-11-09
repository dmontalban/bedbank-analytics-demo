-- FY2026 budget vs actual net revenue, by month and market.
with actual as (

    select month_start, market_code, sum(net_revenue_eur) as actual_revenue_eur
    from {{ ref('mart_revenue_cube') }}
    where year(month_start) = 2026
    group by 1, 2

)

select
    b.month_start,
    b.market_code,
    b.budget_revenue_eur,
    a.actual_revenue_eur,
    a.actual_revenue_eur - b.budget_revenue_eur                       as variance_eur,
    a.actual_revenue_eur / nullif(b.budget_revenue_eur, 0) - 1        as variance_pct
from {{ ref('stg_budget') }} as b
left join actual as a
    on a.month_start = b.month_start
   and a.market_code = b.market_code
