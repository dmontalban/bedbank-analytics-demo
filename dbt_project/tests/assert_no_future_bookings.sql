select * from {{ ref('fct_bookings') }}
where booking_date > cast('{{ var("data_cutoff") }}' as date)
