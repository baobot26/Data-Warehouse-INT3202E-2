-- db/migration/V2__create_facts_and_indexes.sql

CREATE TABLE IF NOT EXISTS dw.fact_sales (
    order_id TEXT PRIMARY KEY,
    customer_key BIGINT NOT NULL REFERENCES dw.dim_customer (customer_key),
    retailer_key BIGINT NOT NULL REFERENCES dw.dim_retailer (retailer_key),
    product_key BIGINT NOT NULL REFERENCES dw.dim_product (product_key),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    discount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (discount >= 0),
    tax NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (tax >= 0),
    date_key INTEGER NOT NULL REFERENCES dw.dim_date (date_key),
    address_key BIGINT NOT NULL REFERENCES dw.dim_address (address_key),
    payment_key BIGINT NOT NULL REFERENCES dw.dim_payment (payment_key),
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fact_sales_customer_key ON dw.fact_sales (customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_retailer_key ON dw.fact_sales (retailer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product_key ON dw.fact_sales (product_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_date_key ON dw.fact_sales (date_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_address_key ON dw.fact_sales (address_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_payment_key ON dw.fact_sales (payment_key);
