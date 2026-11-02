{#
  A team name reduced to what stays the same between providers: lower case, no accents, no
  punctuation, single spaces. "Grêmio F.B.P.A." and "gremio fbpa" give the same key.
#}
{% macro name_key(expression) -%}
    nullif(trim(regexp_replace(lower(strip_accents({{ expression }})), '[^a-z0-9]+', ' ', 'g')), '')
{%- endmacro %}
