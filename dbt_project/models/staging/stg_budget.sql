select
    cast(fiscal_year as integer)              as fiscal_year,
    cast(month_start as date)                 as month_start,
    upper(trim(market_code))                  as market_code,
    cast(budget_revenue_eur as double)        as budget_revenue_eur
from {{ source('raw', 'budget') }}
