-- 12 months x 8 markets
select 1 as problem
from (select count(*) as n from {{ ref('mart_budget_vs_actual') }})
where n <> 96
