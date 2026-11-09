-- The cube must add up to the fact table, to the cent.
select *
from (
    select
        (select sum(net_revenue_eur) from {{ ref('fct_bookings') }})       as fct_revenue,
        (select sum(net_revenue_eur) from {{ ref('mart_revenue_cube') }})  as cube_revenue,
        (select count(*) from {{ ref('fct_bookings') }})                   as fct_bookings,
        (select sum(gross_bookings) from {{ ref('mart_revenue_cube') }})   as cube_bookings
)
where abs(fct_revenue - cube_revenue) > 0.01
   or fct_bookings <> cube_bookings
