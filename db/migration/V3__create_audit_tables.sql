CREATE TABLE IF NOT EXISTS dw.etl_job_audit (
    job_id BIGSERIAL PRIMARY KEY,
    job_name TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('SUCCESS','FAILED','RUNNING')),
    records_processed INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dw.etl_error_records (
    error_id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL REFERENCES dw.etl_job_audit(job_id),
    source_system TEXT NOT NULL,
    record_data JSONB NOT NULL,
    error_message TEXT NOT NULL,
    error_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
