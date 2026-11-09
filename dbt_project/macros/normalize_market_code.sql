{# The feed mixes 'UK', 'GB', 'uk', 'UK ' ... One code per market, whatever the sender typed. #}
{% macro normalize_market_code(column_name) %}
    case upper(trim({{ column_name }}))
        when 'GB' then 'UK'
        else upper(trim({{ column_name }}))
    end
{% endmacro %}
