{#
  Data-quality log: what the staging layer fixed, in numbers. Row 4 proves nothing was lost silently.
#}
with raw_bookings as (

    select * from {{ source('raw', 'bookings') }}

),

counts as (

    select
        (select count(*) from raw_bookings)                                                                 as raw_rows,
        (select count(*) - count(distinct booking_id) from raw_bookings)                                    as duplicate_rows,
        (select count(*) from raw_bookings
          where market_code <> {{ normalize_market_code('market_code') }})                                  as market_code_rows_normalised,
        (select count(distinct booking_id) from raw_bookings where cast(ttv_eur as double) <= 0)            as zero_value_bookings,
        (select count(*) from {{ ref('fct_bookings') }})                                                    as fct_rows

)

select 1 as check_id, 'Replayed feed batch'        as check_name, 'Keep the latest delivery per booking_id'                          as rule_applied, duplicate_rows               as rows_affected, raw_rows from counts
union all
select 2,             'Inconsistent market codes', 'Trim, upper-case, map GB to UK',                                                                  market_code_rows_normalised,                  raw_rows from counts
union all
select 3,             'Zero-value test bookings',  'Exclude bookings with TTV <= 0',                                                                  zero_value_bookings,                          raw_rows from counts
union all
select 4,             'Reconciliation',            'raw rows - duplicates - zero-value - rows in fct_bookings (0 = fully reconciled)',                raw_rows - duplicate_rows - zero_value_bookings - fct_rows, raw_rows from counts
