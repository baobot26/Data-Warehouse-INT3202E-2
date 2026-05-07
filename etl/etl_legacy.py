import os
import json
import logging
from datetime import datetime
from decimal import Decimal
from pymongo import MongoClient
from psycopg import connect, rows

# --- CONFIGURATION ---
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("ETL_AUDIT")

def get_env(name):
    return os.getenv(name)

# --- UTILS ---
def to_decimal(value):
    return Decimal(str(value))

def normalize_timestamp(value):
    if isinstance(value, datetime): return value
    if isinstance(value, str): return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError(f"Unsupported sold_at type: {type(value)}")

# --- AUDIT SERVICES ---
def log_job_start(pg_conn, job_name):
    with pg_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO dw.etl_job_audit (job_name, status, start_time)
            VALUES (%s, 'RUNNING', NOW())
            RETURNING job_id;
        """, (job_name,))
        return cur.fetchone()[0]

def log_job_end(pg_conn, job_id, status, records_processed, error_count, error_msg=None):
    with pg_conn.cursor() as cur:
        cur.execute("""
            UPDATE dw.etl_job_audit
            SET end_time = NOW(), status = %s,
                records_processed = %s, error_count = %s, error_message = %s
            WHERE job_id = %s;
        """, (status, records_processed, error_count, error_msg, job_id))

def log_error_record(pg_conn, job_id, record_data, error_message):
    with pg_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO dw.etl_error_records (job_id, source_system, record_data, error_message)
            VALUES (%s, 'MONGODB', %s, %s);
        """, (job_id, json.dumps(record_data, default=str), error_message))

# --- ETL PHASES ---

def extract_from_mongo():
    mongo_uri = f"mongodb://{get_env('MONGO_INITDB_ROOT_USERNAME')}:{get_env('MONGO_INITDB_ROOT_PASSWORD')}@{get_env('MONGO_HOST')}:{get_env('MONGO_PORT')}/?authSource=admin"
    client = MongoClient(mongo_uri)
    db = client[get_env('MONGO_DB')]
    # Dùng cursor để tối ưu RAM thay vì .list()
    return db["orders_raw"].find(), client

def transform_record(record):
    """Làm sạch và chuẩn hóa dữ liệu trước khi nạp"""
    transformed = record.copy()
    transformed['sold_at'] = normalize_timestamp(record['sold_at'])
    transformed['price'] = to_decimal(record['price'])
    # Bạn có thể thêm các bước validate logic ở đây
    return transformed

def load_to_postgres(cur, data):
    """Thực hiện UPSERT vào Data Warehouse"""
    # Lưu ý: Code này kế thừa các hàm upsert_customer, upsert_fact... từ bản cũ của bạn
    # Ở đây mình viết gọn lại đại diện cho logic Load
    cur.execute("""
        INSERT INTO dw.fact_sales (order_id, price, loaded_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (order_id) DO UPDATE SET price = EXCLUDED.price;
    """, (data['order_id'], data['price']))

# --- MAIN ORCHESTRATOR ---
def run_etl():
    pg_conn = connect(
        host=get_env("PGHOST"),
        dbname=get_env("POSTGRES_DB"),
        user=get_env("POSTGRES_USER"),
        password=get_env("POSTGRES_PASSWORD")
    )
    
    job_id = log_job_start(pg_conn, "MONGO_TO_PG_SALES")
    mongo_cursor, mongo_client = extract_from_mongo()
    
    success_count = 0
    error_count = 0

    try:
        for record in mongo_cursor:
            try:
                # Bọc mỗi bản ghi trong 1 transaction riêng hoặc savepoint 
                # để lỗi 1 dòng không hỏng cả mẻ
                with pg_conn.transaction():
                    with pg_conn.cursor() as cur:
                        clean_data = transform_record(record)
                        load_to_postgres(cur, clean_data)
                        success_count += 1
            except Exception as e:
                error_count += 1
                log_error_record(pg_conn, job_id, record, str(e))
                pg_conn.commit() # Lưu vết lỗi vào DB ngay lập tức
                logger.warning(f"Record failed: {record.get('order_id')} - {str(e)}")

        log_job_end(pg_conn, job_id, 'SUCCESS', success_count, error_count)
        logger.info(f"ETL Finished. Success: {success_count}, Fail: {error_count}")

    except Exception as fatal_e:
        log_job_end(pg_conn, job_id, 'FAILED', success_count, error_count, str(fatal_e))
        logger.error(f"Fatal ETL Error: {str(fatal_e)}")
    
    finally:
        mongo_client.close()
        pg_conn.close()

if __name__ == "__main__":
    run_etl()