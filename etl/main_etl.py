import os
import argparse
from pathlib import Path
from dotenv import load_dotenv
from psycopg import connect

# --- IMPORT CÁC MODULE NỘI BỘ ---
from etl.extract import extract_orders
from etl.transform import transform_order
from etl.load import upsert_fact_sale
from etl.audit import log_job_start, log_job_end, log_error
from etl.utils import require_env

# 1. Nạp biến môi trường từ file .env ngay khi khởi động
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# --- HÀM TRỢ GIÚP: QUẢN LÝ WATERMARK ---
def get_watermark(conn, source_name):
    """Đọc mốc thời gian lấy dữ liệu cuối cùng từ Postgres"""
    with conn.cursor() as cur:
        cur.execute("SELECT last_value FROM etl_watermark WHERE source_name = %s", (source_name,))
        result = cur.fetchone()
        return result[0] if result else None

def update_watermark(conn, source_name, new_watermark):
    """Cập nhật mốc thời gian mới vào Postgres"""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO etl_watermark (source_name, last_value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (source_name)
            DO UPDATE SET last_value = EXCLUDED.last_value, updated_at = NOW();
        """, (source_name, new_watermark))

def run_etl(full_refresh=False):
    print("🚀 --- KHỞI ĐỘNG TIẾN TRÌNH ETL (INCREMENTAL) ---")
    
    try:
        conn = connect(
            host=require_env("PGHOST"),
            port=int(require_env("PGPORT")),
            dbname=require_env("POSTGRES_DB"),
            user=require_env("POSTGRES_USER"),
            password=require_env("POSTGRES_PASSWORD"),
            autocommit=True
        )
    except Exception as e:
        print(f"❌ Lỗi kết nối Database: {e}")
        return

    job_id = log_job_start(conn, "daily_sales_etl_incremental")
    success_count = 0
    error_count = 0

    try:
        current_watermark = None if full_refresh else get_watermark(conn, "orders")
        print(f"💧 Watermark hiện tại (Cột mốc): {current_watermark}")

        print("📦 [1/3] Đang Extract dữ liệu từ MongoDB...")
        raw_orders = extract_orders(current_watermark) 
        latest_watermark = current_watermark

        with conn.cursor() as cur:
            for order in raw_orders:
                try:
                    clean_order = transform_order(order)
                    upsert_fact_sale(cur, clean_order)
                    
                    success_count += 1
                    if success_count % 10 == 0:
                        print(f"--- Đã nạp thành công {success_count} bản ghi...")

                    doc_time = order.get("updated_at")
                    if not doc_time and "_id" in order:
                        doc_time = order["_id"].generation_time.replace(tzinfo=None)
                    
                    if doc_time and (latest_watermark is None or doc_time > latest_watermark):
                        latest_watermark = doc_time

                except Exception as e:
                    error_count += 1
                    log_error(conn, job_id, "TRANSFORM_OR_LOAD", order, str(e))
                    print(f"⚠️ Lỗi bản ghi {order.get('order_id', 'unknown')}: {e}")

        if latest_watermark and latest_watermark != current_watermark:
            update_watermark(conn, "orders", latest_watermark)
            print(f"📈 Đã lưu Watermark mới thành công: {latest_watermark}")

        log_job_end(conn, job_id, "SUCCESS", success_count, error_count)
        print("\n" + "="*40)
        print(f"✨ TIẾN TRÌNH ETL HOÀN TẤT ✨")
        print(f"✅ Thành công: {success_count}")
        print(f"❌ Thất bại:   {error_count}")
        print("="*40)

    except Exception as fatal_e:
        print(f"🔥 LỖI HỆ THỐNG NGHIÊM TRỌNG: {fatal_e}")
        log_job_end(conn, job_id, "FAILED", success_count, error_count)

    finally:
        conn.close()
        print("🔌 Đã đóng kết nối Database.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-refresh", action="store_true", help="Bỏ qua watermark, load lại từ đầu")
    args = parser.parse_args()
    
    run_etl(full_refresh=args.full_refresh)