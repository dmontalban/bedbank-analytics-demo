-- volume + mix + price + rate must equal the change in revenue (residual ~ 0).
select * from {{ ref('mart_revenue_bridge') }}
where abs(residual) > 0.01
