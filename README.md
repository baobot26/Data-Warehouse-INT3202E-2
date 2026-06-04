# Data-Warehouse-INT3202E-2

Kho dữ liệu mẫu chạy bằng Docker cho bài toán Olist star schema. Sau đợt refactor gần đây, toàn bộ mã nguồn chuẩn của dự án đã được gom vào thư mục `core/`.

## 1. Cấu trúc dự án

Phần `core/` là nơi chứa toàn bộ logic chính:

- `core/etl/`: logic ETL, bao gồm import Olist vào MongoDB, xử lý Bronze/Silver/Gold, data quality và SCD2
- `core/dashboard/`: ứng dụng dashboard đọc dữ liệu từ PostgreSQL
- `core/db/`: script khởi tạo schema và migration cho PostgreSQL
- `core/mongo-init.js`: script khởi tạo MongoDB
- `core/Dockerfile`: image dùng chung cho ETL, dashboard và pipeline import

Các thư mục source cũ ở root như `dashboard/`, `etl/`, `db/` đã được loại bỏ khỏi luồng chạy chính.

## 2. Yêu cầu hệ thống

Trước khi chạy dự án, bạn cần:

- Docker Desktop hoặc Docker Engine đang hoạt động
- File `.env` ở thư mục gốc, tạo từ `.env.example`
- Dữ liệu thô Olist nằm trong `data/olist/raw/`

PowerShell:

```powershell
Copy-Item .env.example .env
```

Bash:

```bash
cp .env.example .env
```

Dữ liệu Olist cần có:

```text
data/olist/raw/olist_orders_dataset.csv
data/olist/raw/olist_order_items_dataset.csv
data/olist/raw/olist_customers_dataset.csv
data/olist/raw/olist_products_dataset.csv
data/olist/raw/olist_sellers_dataset.csv
data/olist/raw/olist_order_payments_dataset.csv
data/olist/raw/product_category_name_translation.csv
```

## 3. Kiến trúc vận hành

Luồng dữ liệu của dự án:

1. Olist raw CSV được import vào MongoDB.
2. ETL đọc dữ liệu từ MongoDB và nạp tuần tự vào `bronze`, `silver`, rồi `dw`.
3. Dashboard đọc dữ liệu từ PostgreSQL để hiển thị số liệu Gold, trạng thái batch và kết quả DQ.

Các bảng chính trong PostgreSQL:

- `bronze.orders_raw`
- `silver.orders_clean`
- `silver.orders_rejected`
- `etl.batch_run`
- `dq.check_results`
- `dw.fact_sales`
- `dw.dim_customer`
- `dw.dim_product`
- `dw.dim_retailer`
- `dw.dim_address`
- `dw.dim_payment`
- `dw.dim_date`

## 4. Hướng dẫn chạy

### 4.1 Full Run

Đây là chế độ chạy đầy đủ, phù hợp khi bạn muốn import Olist từ đầu và chạy toàn bộ pipeline.

```powershell
docker compose --profile tools run --rm olist-pipeline
```

Trong container, pipeline sẽ thực hiện:

- `python -m core.etl.import_olist_to_mongo`
- `python -m core.etl.main_etl`

### 4.2 Limited Run

Chế độ này giới hạn số lượng bản ghi bằng biến môi trường `OLIST_LIMIT`, rất hữu ích khi bạn muốn test nhanh hoặc tiết kiệm tài nguyên.

PowerShell:

```powershell
$env:OLIST_LIMIT = 100
docker compose --profile tools run --rm olist-pipeline
Remove-Item Env:OLIST_LIMIT
```

Bash:

```bash
OLIST_LIMIT=100 docker compose --profile tools run --rm olist-pipeline
```

Ghi chú:

- `OLIST_LIMIT=0` hoặc không đặt biến này nghĩa là chạy toàn bộ dữ liệu.
- Bạn cũng có thể khai báo `OLIST_LIMIT` trong file `.env` nếu muốn dùng thường xuyên.

### 4.3 Rerun ETL

Dùng khi dữ liệu thô đã có sẵn trong MongoDB và bạn chỉ muốn chạy lại phần ETL sang PostgreSQL.

```powershell
docker compose run --rm etl
```

Lệnh này sẽ chạy `python -m core.etl.main_etl` trong container.

## 5. Ghi chú kỹ thuật

Dự án hiện đã được tối ưu để xử lý dữ liệu lớn ổn định hơn:

- Gold layer dùng batch-processing, xử lý theo lô 1000 dòng
- transaction được commit theo batch để tránh giữ kết nối quá lâu
- khi có lỗi sẽ rollback để giải phóng transaction
- log có `flush=True` để hiển thị ngay trong container

Những cải tiến này giúp pipeline tránh tình trạng treo khi xử lý khối lượng lớn như 110k bản ghi.

## 6. Cách kiểm tra sau khi chạy

Mở dashboard:

```text
http://localhost:8501
```

Kiểm tra trạng thái batch gần nhất:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT status, extracted_count, silver_accepted_count, silver_rejected_count, gold_loaded_count, finished_at - started_at AS elapsed FROM etl.batch_run ORDER BY started_at DESC LIMIT 1;"
```

Kiểm tra số dòng trong Gold fact:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT COUNT(*) AS fact_sales_rows FROM dw.fact_sales;"
```

Kiểm tra dữ liệu trong `dw.fact_sales`:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT order_id, quantity, price, discount, tax, batch_id, silver_id FROM dw.fact_sales ORDER BY loaded_at DESC LIMIT 20;"
```

Kiểm tra batch và data quality gần nhất:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT layer, check_name, status, severity, checked_count, failed_count, details FROM dq.check_results WHERE batch_id = (SELECT batch_id FROM etl.batch_run ORDER BY started_at DESC LIMIT 1) ORDER BY layer, check_name;"
```

## 7. File quan trọng

- `docker-compose.yml`: khai báo toàn bộ stack và trỏ tới các file trong `core/`
- `core/Dockerfile`: image chung cho dashboard và ETL
- `core/dashboard/app.py`: dashboard web
- `core/etl/main_etl.py`: entrypoint ETL
- `core/etl/etl_legacy.py`: luồng Bronze/Silver/Gold chính
- `core/etl/load.py`: logic load Gold và SCD2
- `core/etl/import_olist_to_mongo.py`: import Olist CSV vào MongoDB
- `core/etl/dq.py`: data quality
- `core/etl/extract.py`, `core/etl/transform.py`, `core/etl/utils.py`: helper ETL
- `core/db/init.sql`: bootstrap schema cho PostgreSQL
- `core/db/migration/*.sql`: migration schema
- `core/db/tests/scd2_dim_customer_checks.sql`: kiểm tra hồi quy SCD2
- `core/mongo-init.js`: bootstrap MongoDB

## 8. Khắc phục sự cố

Nếu gặp lỗi `ModuleNotFoundError`, hãy kiểm tra:

- `docker-compose.yml` đang trỏ tới `core/Dockerfile`
- dashboard dùng `python -m core.dashboard.app`
- ETL dùng `python -m core.etl.main_etl`

Nếu thiếu dữ liệu Olist, hãy xác nhận các file CSV nằm đúng trong `data/olist/raw/`.

Nếu muốn chạy lại từ đầu với database sạch:

```powershell
docker compose down -v
```
