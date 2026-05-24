CREATE TABLE IF NOT EXISTS etl_watermark (
    source_name TEXT PRIMARY KEY,
    last_value TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);