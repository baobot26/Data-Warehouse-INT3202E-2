def log_job_start(conn, job_name):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO dw.etl_job_audit (job_name, status, start_time)
            VALUES (%s, 'RUNNING', NOW())
            RETURNING job_id;
        """, (job_name,))
        job_id = cur.fetchone()[0]
        conn.commit()
        return job_id

def log_job_end(conn, job_id, status, records_processed=0, error_count=0):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE dw.etl_job_audit
            SET end_time = NOW(), status = %s,
                records_processed = %s, error_count = %s
            WHERE job_id = %s;
        """, (status, records_processed, error_count, job_id))
        conn.commit()

def log_error(conn, job_id, source_system, record_data, error_message):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO dw.etl_error_records (job_id, source_system, record_data, error_message)
            VALUES (%s, %s, %s, %s);
        """, (job_id, source_system, record_data, error_message))
        conn.commit()
