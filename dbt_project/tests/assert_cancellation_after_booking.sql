select * from {{ ref('fct_bookings') }}
where is_cancelled and (cancelled_at is null or cancelled_at < booking_ts)
