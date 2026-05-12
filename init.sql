BEGIN;

CREATE SCHEMA IF NOT EXISTS etl;
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS dw;

CREATE TABLE IF NOT EXISTS etl.batch_run (
    batch_id UUID PRIMARY KEY,
    pipeline_name TEXT NOT NULL DEFAULT 'orders',
    source_database TEXT NOT NULL DEFAULT 'landing',
    source_collection TEXT NOT NULL DEFAULT 'orders_raw',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    bronze_completed_at TIMESTAMPTZ,
    silver_completed_at TIMESTAMPTZ,
    gold_completed_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    error_message TEXT,
    extracted_count BIGINT NOT NULL DEFAULT 0,
    silver_accepted_count BIGINT NOT NULL DEFAULT 0,
    silver_rejected_count BIGINT NOT NULL DEFAULT 0,
    gold_loaded_count BIGINT NOT NULL DEFAULT 0,
    CONSTRAINT ck_batch_run_status
        CHECK (status IN ('running', 'failed', 'success'))
);

CREATE INDEX IF NOT EXISTS idx_batch_run_started
    ON etl.batch_run (pipeline_name, started_at DESC);

CREATE TABLE IF NOT EXISTS bronze.orders_raw (
    bronze_id BIGSERIAL PRIMARY KEY,
    batch_id UUID NOT NULL REFERENCES etl.batch_run (batch_id),
    mongo_id TEXT NOT NULL,
    source_collection TEXT NOT NULL DEFAULT 'orders_raw',
    payload JSONB NOT NULL,
    payload_hash TEXT NOT NULL,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (batch_id, mongo_id)
);

CREATE INDEX IF NOT EXISTS idx_bronze_orders_batch
    ON bronze.orders_raw (batch_id);

CREATE INDEX IF NOT EXISTS idx_bronze_orders_order_id
    ON bronze.orders_raw ((payload ->> 'order_id'));

CREATE TABLE IF NOT EXISTS silver.orders_clean (
    silver_id BIGSERIAL PRIMARY KEY,
    bronze_id BIGINT NOT NULL UNIQUE REFERENCES bronze.orders_raw (bronze_id),
    batch_id UUID NOT NULL REFERENCES etl.batch_run (batch_id),
    mongo_id TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    order_id TEXT NOT NULL,
    sold_at TIMESTAMPTZ NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    discount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (discount >= 0),
    tax NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (tax >= 0),
    customer_id TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    customer_phone_number TEXT,
    customer_email TEXT,
    customer_membership TEXT,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    product_category TEXT,
    product_brand TEXT,
    quantity_in_stock INTEGER,
    retailer_id TEXT NOT NULL,
    retailer_name TEXT NOT NULL,
    retailer_phone_number TEXT,
    retailer_email TEXT,
    retailer_rating NUMERIC(3,2),
    street TEXT NOT NULL,
    commune_ward TEXT NOT NULL,
    province_city TEXT NOT NULL,
    payment_type TEXT NOT NULL,
    method_provider TEXT NOT NULL,
    cleaned_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_silver_orders_batch
    ON silver.orders_clean (batch_id);

CREATE INDEX IF NOT EXISTS idx_silver_orders_order_id
    ON silver.orders_clean (order_id);

CREATE TABLE IF NOT EXISTS silver.orders_rejected (
    rejected_id BIGSERIAL PRIMARY KEY,
    bronze_id BIGINT NOT NULL UNIQUE REFERENCES bronze.orders_raw (bronze_id),
    batch_id UUID NOT NULL REFERENCES etl.batch_run (batch_id),
    mongo_id TEXT NOT NULL,
    order_id TEXT,
    reject_reason TEXT NOT NULL,
    rejected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_silver_orders_rejected_batch
    ON silver.orders_rejected (batch_id);

CREATE TABLE IF NOT EXISTS dw.dim_customer (
    customer_key BIGSERIAL PRIMARY KEY,
    customer_id TEXT NOT NULL UNIQUE,
    customer_name TEXT NOT NULL,
    phone_number TEXT,
    email TEXT,
    membership TEXT
);

CREATE TABLE IF NOT EXISTS dw.dim_product (
    product_key BIGSERIAL PRIMARY KEY,
    product_id TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    product_category TEXT,
    product_brand TEXT,
    quantity_in_stock INTEGER
);

CREATE TABLE IF NOT EXISTS dw.dim_retailer (
    retailer_key BIGSERIAL PRIMARY KEY,
    retailer_id TEXT NOT NULL UNIQUE,
    retailer_name TEXT NOT NULL,
    phone_number TEXT,
    email TEXT,
    rating NUMERIC(3,2)
);

CREATE TABLE IF NOT EXISTS dw.dim_address (
    address_key BIGSERIAL PRIMARY KEY,
    street TEXT NOT NULL,
    commune_ward TEXT NOT NULL,
    province_city TEXT NOT NULL,
    UNIQUE (street, commune_ward, province_city)
);

CREATE TABLE IF NOT EXISTS dw.dim_payment (
    payment_key BIGSERIAL PRIMARY KEY,
    payment_type TEXT NOT NULL,
    method_provider TEXT NOT NULL,
    UNIQUE (payment_type, method_provider)
);

CREATE TABLE IF NOT EXISTS dw.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    day SMALLINT NOT NULL,
    month SMALLINT NOT NULL,
    year INTEGER NOT NULL
);

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
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    batch_id UUID REFERENCES etl.batch_run (batch_id),
    silver_id BIGINT REFERENCES silver.orders_clean (silver_id)
);

ALTER TABLE dw.fact_sales
    ADD COLUMN IF NOT EXISTS batch_id UUID REFERENCES etl.batch_run (batch_id);

ALTER TABLE dw.fact_sales
    ADD COLUMN IF NOT EXISTS silver_id BIGINT REFERENCES silver.orders_clean (silver_id);

CREATE INDEX IF NOT EXISTS idx_fact_sales_customer_key ON dw.fact_sales (customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_retailer_key ON dw.fact_sales (retailer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product_key ON dw.fact_sales (product_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_date_key ON dw.fact_sales (date_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_address_key ON dw.fact_sales (address_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_payment_key ON dw.fact_sales (payment_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_batch_id ON dw.fact_sales (batch_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_silver_id ON dw.fact_sales (silver_id);

COMMIT;
