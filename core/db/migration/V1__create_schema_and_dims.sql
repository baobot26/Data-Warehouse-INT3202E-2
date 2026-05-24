-- db/migration/V1__create_schema_and_dims.sql

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
