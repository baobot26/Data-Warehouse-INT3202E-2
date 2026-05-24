BEGIN;

ALTER TABLE dw.dim_customer
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS is_current BOOLEAN;

UPDATE dw.dim_customer
SET valid_from = COALESCE(valid_from, NOW()),
    is_current = COALESCE(is_current, TRUE);

ALTER TABLE dw.dim_customer
    ALTER COLUMN valid_from SET DEFAULT NOW(),
    ALTER COLUMN valid_from SET NOT NULL,
    ALTER COLUMN is_current SET DEFAULT TRUE,
    ALTER COLUMN is_current SET NOT NULL;

ALTER TABLE dw.dim_customer
    DROP CONSTRAINT IF EXISTS dim_customer_customer_id_key;

DROP INDEX IF EXISTS dw.dim_customer_customer_id_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_customer_current
    ON dw.dim_customer (customer_id)
    WHERE is_current;

CREATE INDEX IF NOT EXISTS idx_dim_customer_customer_id_valid_from
    ON dw.dim_customer (customer_id, valid_from DESC);

ALTER TABLE dw.dim_customer
    DROP CONSTRAINT IF EXISTS ck_dim_customer_scd2_validity;

ALTER TABLE dw.dim_customer
    ADD CONSTRAINT ck_dim_customer_scd2_validity
    CHECK (
        (is_current = TRUE AND valid_to IS NULL)
        OR (is_current = FALSE AND valid_to IS NOT NULL)
    );

COMMIT;
