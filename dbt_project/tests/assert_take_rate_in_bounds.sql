-- Every cell's take rate must sit in a plausible commercial range (3% - 30%).
select *, net_revenue_eur / net_ttv_eur as take_rate
from {{ ref('mart_revenue_cube') }}
where net_revenue_eur / net_ttv_eur not between 0.03 and 0.30
