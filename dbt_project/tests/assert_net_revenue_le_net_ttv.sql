-- Revenue (margin) can never exceed the transaction value it is earned on.
select * from {{ ref('mart_revenue_cube') }}
where net_revenue_eur > net_ttv_eur
