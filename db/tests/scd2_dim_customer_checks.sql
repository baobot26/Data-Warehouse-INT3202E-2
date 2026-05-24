-- Check 1: No business key should have more than one current row.
SELECT
    customer_id,
    COUNT(*) AS current_row_count
FROM dw.dim_customer
WHERE is_current = TRUE
GROUP BY customer_id
HAVING COUNT(*) > 1;

-- Check 2: No SCD2 period overlap for the same business key.
SELECT
    a.customer_id,
    a.customer_key AS customer_key_left,
    b.customer_key AS customer_key_right,
    a.valid_from AS left_valid_from,
    a.valid_to AS left_valid_to,
    b.valid_from AS right_valid_from,
    b.valid_to AS right_valid_to
FROM dw.dim_customer a
JOIN dw.dim_customer b
  ON a.customer_id = b.customer_id
 AND a.customer_key < b.customer_key
 AND tsrange(a.valid_from, COALESCE(a.valid_to, 'infinity'::timestamptz), '[)')
     && tsrange(b.valid_from, COALESCE(b.valid_to, 'infinity'::timestamptz), '[)');

-- Check 3: Current rows must keep valid_to as NULL.
SELECT
    customer_key,
    customer_id,
    valid_from,
    valid_to,
    is_current
FROM dw.dim_customer
WHERE is_current = TRUE
  AND valid_to IS NOT NULL;
