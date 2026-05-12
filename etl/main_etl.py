import os
import json
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

def run_etl():
    print("🚀 --- KHỞI ĐỘNG TIẾN TRÌNH ETL (E-T-L) ---")
    
    # 2. Kết nối tới Database Postgres (Target)
    try:
        conn = connect(
            host=require_env("PGHOST"),
            port=int(require_env("PGPORT")),
            dbname=require_env("POSTGRES_DB"),
            user=require_env("POSTGRES_USER"),
            password=require_env("POSTGRES_PASSWORD"),
            autocommit=True  # Quan trọng để ghi log audit và lỗi ngay lập tức
        )
    except Exception as e:
        print(f"❌ Lỗi kết nối Database: {e}")
        return

    # 3. Khởi tạo phiên làm việc (Audit Job)
    job_id = log_job_start(conn, "daily_sales_etl_full")
    success_count = 0
    error_count = 0

    try:
        # --- BƯỚC 1: EXTRACT (Lấy dữ liệu từ MongoDB) ---
        print("📦 [1/3] Đang Extract dữ liệu từ MongoDB...")
        raw_orders = extract_orders()
        print(f"✅ Đã lấy được {len(raw_orders)} bản ghi thô.")

        with conn.cursor() as cur:
            for order in raw_orders:
                try:
                    # --- BƯỚC 2: TRANSFORM (Chuẩn hóa dữ liệu) ---
                    # Bước này xử lý ngày tháng, ép kiểu số, xử lý null/mặc định
                    clean_order = transform_order(order)
                    
                    # --- BƯỚC 3: LOAD (Nạp vào Postgres Star Schema) ---
                    # Bước này thực hiện UPSERT vào các bảng Dim và Fact
                    upsert_fact_sale(cur, clean_order)
                    
                    success_count += 1
                    if success_count % 10 == 0:
                        print(f"--- Đã nạp thành công {success_count} bản ghi...")

                except Exception as e:
                    # Ghi lại lỗi chi tiết cho từng bản ghi mà không làm sập cả pipeline
                    error_count += 1
                    log_error(conn, job_id, "TRANSFORM_OR_LOAD", order, str(e))
                    print(f"⚠️ Lỗi bản ghi {order.get('order_id', 'unknown')}: {e}")

        # 4. Ghi nhận hoàn thành thành công
        log_job_end(conn, job_id, "SUCCESS", success_count, error_count)
        print("\n" + "="*40)
        print(f"✨ TIẾN TRÌNH ETL HOÀN TẤT ✨")
        print(f"✅ Thành công: {success_count}")
        print(f"❌ Thất bại:   {error_count}")
        print("="*40)

    except Exception as fatal_e:
        # Xử lý lỗi nghiêm trọng (ví dụ mất kết nối mạng giữa chừng)
        print(f"🔥 LỖI HỆ THỐNG NGHIÊM TRỌNG: {fatal_e}")
        log_job_end(conn, job_id, "FAILED", success_count, error_count)

    finally:
        conn.close()
        print("🔌 Đã đóng kết nối Database.")

if __name__ == "__main__":
    run_etl()