-- The bridge needs every cell to exist in every month: 8 markets x 4 segments x 3 tiers = 96 cells.
select month_start, count(*) as n_cells
from {{ ref('mart_revenue_cube') }}
group by 1
having count(*) <> 96
