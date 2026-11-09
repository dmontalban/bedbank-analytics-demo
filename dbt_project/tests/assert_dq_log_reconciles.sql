-- Check 4 of the data-quality log must be exactly zero: no row is lost without a reason.
select * from {{ ref('dq_log') }}
where check_id = 4 and rows_affected <> 0
