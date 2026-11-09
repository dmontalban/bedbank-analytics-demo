{#
  One row per booking_id, typed and cleaned.
  Rules (each one is counted in marts.dq_log):
    1. replayed batches  -> keep the latest delivery per booking_id
    2. market code noise -> normalise (trim, upper-case, GB -> UK)
    3. test bookings     -> drop rows with TTV <= 0
#}
with source as (

    select * from {{ source('raw', 'bookings') }}

),

typed as (

    select
        booking_id,
        cast(booking_ts as timestamp)                 as booking_ts,
        cast(checkin_date as date)                    as checkin_date,
        cast(nights as integer)                       as nights,
        {{ normalize_market_code('market_code') }}    as market_code,
        upper(trim(segment_code))                     as segment_code,
        upper(trim(supplier_tier_code))               as supplier_tier_code,
        customer_id,
        cast(ttv_eur as decimal(18, 2))               as ttv_eur,
        cast(revenue_eur as decimal(18, 2))           as revenue_eur,
        lower(trim(status))                           as status,
        cast(cancelled_at as timestamp)               as cancelled_at,
        cast(loaded_at as timestamp)                  as loaded_at,
        feed_batch
    from source

),

latest_delivery as (

    select *
    from typed
    qualify row_number() over (partition by booking_id order by loaded_at desc) = 1

)

select
    booking_id,
    booking_ts,
    cast(booking_ts as date)                          as booking_date,
    cast(date_trunc('month', booking_ts) as date)     as booking_month,
    checkin_date,
    nights,
    market_code,
    segment_code,
    supplier_tier_code,
    customer_id,
    ttv_eur,
    revenue_eur,
    status,
    (status = 'cancelled')                            as is_cancelled,
    cancelled_at,
    loaded_at,
    feed_batch
from latest_delivery
where ttv_eur > 0
