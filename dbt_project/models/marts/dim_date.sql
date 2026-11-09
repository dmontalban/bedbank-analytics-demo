with days as (
    select cast(d as date) as date_day
    from generate_series(date '2024-01-01', date '2027-12-31', interval 1 day) as t(d)
)
select
    date_day,
    year(date_day)                               as year,
    quarter(date_day)                            as quarter,
    month(date_day)                              as month,
    cast(date_trunc('month', date_day) as date)  as month_start,
    strftime(date_day, '%b')                     as month_name,
    isodow(date_day)                             as iso_day_of_week,
    isodow(date_day) >= 6                        as is_weekend
from days
