BEGIN;

CREATE SCHEMA IF NOT EXISTS dw;

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
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fact_sales_customer_key ON dw.fact_sales (customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_retailer_key ON dw.fact_sales (retailer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product_key ON dw.fact_sales (product_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_date_key ON dw.fact_sales (date_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_address_key ON dw.fact_sales (address_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_payment_key ON dw.fact_sales (payment_key);

COMMIT;
