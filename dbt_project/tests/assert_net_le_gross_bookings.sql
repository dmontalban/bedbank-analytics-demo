select * from {{ ref('mart_revenue_cube') }}
where net_bookings > gross_bookings
