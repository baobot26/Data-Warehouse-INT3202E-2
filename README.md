# Data-Warehouse-INT3202E-2

<<<<<<< ours
This repository now includes a runnable starter deployment for the star schema in `Star Schema.drawio`.

Prerequisite:
- Docker Desktop or another Docker Engine must be running before you start the stack.
- Create a local `.env` file from `.env.example` before the first run:
=======
Kho dữ liệu mẫu chạy bằng Docker cho bài toán Olist star schema. Sau đợt refactor này, mã nguồn chính nằm trong `core/` và đây là nguồn chuẩn duy nhất của dự án.

## 1. Tổng quan

- `MongoDB` giữ dữ liệu thô của đơn hàng tại `landing.orders_raw`.
- `PostgreSQL` lưu ba lớp dữ liệu:
  - `bronze`: dữ liệu thô đã được nạp vào kho, kèm metadata của batch
  - `silver`: dữ liệu đã chuẩn hóa, lọc lỗi và liên kết ngược về bronze
  - `dw`: lớp Gold, dùng cho phân tích theo star schema
- `core/dashboard/app.py` hiển thị dashboard đọc trực tiếp từ PostgreSQL.
- `etl.batch_run` lưu lịch sử từng lần chạy pipeline.
- `dq.check_results` lưu kết quả kiểm tra chất lượng dữ liệu theo batch.

## 2. Yêu cầu trước khi chạy

- Docker Desktop hoặc Docker Engine phải đang chạy.
- Tạo file `.env` ở thư mục gốc từ `.env.example`.

PowerShell:
>>>>>>> theirs

```powershell
Copy-Item .env.example .env
```

<<<<<<< ours
Olist raw CSV files must be present in `data/olist/raw` before running the pipeline. The repository is expected to include these files for test runs:
=======
Bash:

```bash
cp .env.example .env
```

- Bộ dữ liệu Olist phải nằm trong `data/olist/raw/` trước khi chạy pipeline:
>>>>>>> theirs

```text
data/olist/raw/olist_orders_dataset.csv
data/olist/raw/olist_order_items_dataset.csv
data/olist/raw/olist_customers_dataset.csv
data/olist/raw/olist_products_dataset.csv
data/olist/raw/olist_sellers_dataset.csv
data/olist/raw/olist_order_payments_dataset.csv
data/olist/raw/product_category_name_translation.csv
```

<<<<<<< ours
Architecture:
- `MongoDB` is the source system for raw order documents.
- `PostgreSQL` stores three data layers:
  - `bronze`: append-only raw MongoDB payloads with batch metadata.
  - `silver`: typed clean/rejected order rows linked back to bronze.
  - `dw`: the Gold star schema used for analytics.
- `dashboard` serves a simple browser dashboard for Gold sales, ETL status, and data quality checks.
- `etl.batch_run` records each pipeline run for audit, debugging, and reprocessing.
- `dq.check_results` stores per-batch data quality checks and reconciliation results.

## Schema mapping

The Draw.io file maps to these warehouse tables in PostgreSQL:
=======
## 3. Cấu trúc chính

Các phần quan trọng hiện đã được gom về `core/`:

- `core/dashboard/app.py`: dashboard web
- `core/etl/main_etl.py`: entrypoint của ETL
- `core/etl/etl_legacy.py`: orchestration cho luồng Bronze/Silver/Gold
- `core/etl/load.py`: logic load Gold và SCD2
- `core/etl/import_olist_to_mongo.py`: import CSV Olist vào MongoDB
- `core/etl/dq.py`: kiểm tra dữ liệu và reconciliation
- `core/etl/extract.py`, `core/etl/transform.py`, `core/etl/utils.py`: helper ETL
- `core/db/init.sql`: schema bootstrap cho PostgreSQL volume mới
- `core/db/migration/*.sql`: migration schema
- `core/db/tests/scd2_dim_customer_checks.sql`: kiểm tra hồi quy SCD2
- `core/mongo-init.js`: bootstrap MongoDB
- `core/Dockerfile`: image chung cho dashboard và ETL

Các thư mục source cũ ở root như `dashboard/`, `etl/`, `db/` không còn là nơi chứa code chính.

## 4. Kiến trúc dữ liệu

Luồng dữ liệu chuẩn của dự án:

1. Olist raw CSV được import vào MongoDB.
2. ETL đọc dữ liệu từ MongoDB và nạp lần lượt vào `bronze`, `silver`, rồi `dw`.
3. Dashboard đọc dữ liệu từ PostgreSQL để hiển thị trạng thái batch, số liệu Gold và kết quả DQ.

Một số bảng chính:

>>>>>>> theirs
- `dw.fact_sales`
- `dw.dim_customer`
- `dw.dim_product`
- `dw.dim_retailer`
- `dw.dim_address`
- `dw.dim_payment`
- `dw.dim_date`
<<<<<<< ours

Layering and audit tables:
- `etl.batch_run`
- `bronze.orders_raw`
- `silver.orders_clean`
- `silver.orders_rejected`
- `dq.check_results`

## Start the stack

1. Start from clean database volumes when switching to the Olist-only source.
=======
- `bronze.orders_raw`
- `silver.orders_clean`
- `silver.orders_rejected`
- `etl.batch_run`
- `dq.check_results`

## 5. Khởi động hệ thống

### Bước 1: Reset volume nếu cần môi trường sạch

Khi bạn đổi schema, đổi dataset hoặc muốn chạy lại từ đầu, hãy xóa volume cũ:
>>>>>>> theirs

```powershell
docker compose down -v
```

<<<<<<< ours
2. Start PostgreSQL, MongoDB, and the dashboard:
=======
### Bước 2: Khởi động các service nền

Lệnh dưới đây bật PostgreSQL, MongoDB và dashboard:
>>>>>>> theirs

```powershell
docker compose up -d postgres mongodb dashboard
```

<<<<<<< ours
3. Import the checked-in Olist raw CSV files into MongoDB, and run the ETL:
=======
### Bước 3: Chạy pipeline theo một trong 3 cách

#### Cách 1 (Full)

Chạy toàn bộ pipeline Olist: kiểm tra CSV, import vào MongoDB, sau đó chạy ETL đầy đủ.
>>>>>>> theirs

```powershell
docker compose --profile tools run --rm olist-pipeline
```

<<<<<<< ours
The `olist-pipeline` service runs fully inside Docker:
- verifies the required Olist CSV files exist in `data/olist/raw`;
- imports delivered Olist order items into MongoDB `landing.orders_raw`;
- runs `python -m core.etl.main_etl` to load Bronze, Silver, Gold, DQ, and audit tables.

The importer keeps the existing pipeline intact by converting each Olist order item into one MongoDB raw order document with an `OLIST-` order id. Olist is the only supported source dataset for regular runs in this project. Set `OLIST_LIMIT` in `.env` to a positive number for a smaller test import.

For timing in PowerShell:

```powershell
Measure-Command { docker compose --profile tools run --rm olist-pipeline }
```

4. Rerun only the ETL when MongoDB already has raw Olist data:
=======
Trong container, lệnh này thực thi:

- `python -m core.etl.import_olist_to_mongo`
- `python -m core.etl.main_etl`

Đây là chế độ nên dùng khi bạn muốn chạy đầy đủ từ đầu đến cuối.

#### Cách 2 (Test nhanh / Giới hạn)

Dùng `OLIST_LIMIT` để import một số lượng bản ghi xác định. Chế độ này phù hợp cho smoke test, kiểm tra wiring hoặc debug nhanh.

PowerShell (Windows):

```powershell
$env:OLIST_LIMIT = 100
docker compose --profile tools run --rm olist-pipeline
Remove-Item Env:OLIST_LIMIT
```

Bash (Linux/macOS/Git Bash):

```bash
OLIST_LIMIT=100 docker compose --profile tools run --rm olist-pipeline
```

Ghi chú:

- `OLIST_LIMIT=0` hoặc để trống nghĩa là chạy không giới hạn.
- Nếu muốn giữ giá trị lâu hơn, bạn có thể đặt nó trong `.env`.

#### Cách 3 (Rerun ETL)

Dùng khi MongoDB đã có sẵn raw data và bạn chỉ muốn chạy lại phần ETL, không import lại CSV.
>>>>>>> theirs

```powershell
docker compose run --rm etl
```

<<<<<<< ours
5. Check the warehouse:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT order_id, quantity, price, discount, tax, batch_id, silver_id FROM dw.fact_sales ORDER BY loaded_at DESC LIMIT 20;"
```

Check the latest batch size and runtime:
=======
Lệnh này dùng image trong `core/Dockerfile` và chạy `python -m core.etl.main_etl` trong container.

## 6. Kiểm tra sau khi chạy

Mở dashboard tại:

```text
http://localhost:8501
```

Dashboard sẽ hiển thị:

- số liệu Gold
- trạng thái batch ETL gần nhất
- kết quả kiểm tra chất lượng dữ liệu
- top sản phẩm
- các đơn hàng gần nhất

Kiểm tra batch gần nhất:
>>>>>>> theirs

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT status, extracted_count, silver_accepted_count, silver_rejected_count, gold_loaded_count, finished_at - started_at AS elapsed FROM etl.batch_run ORDER BY started_at DESC LIMIT 1;"
```

<<<<<<< ours
6. Open `http://localhost:8501` to view Gold sales metrics, latest ETL batch status, recent data quality results, top products, and recent orders.

7. Inspect dimensions with a simple join:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT f.order_id, d.full_date, c.customer_name, p.product_name, r.retailer_name FROM dw.fact_sales f JOIN dw.dim_date d ON d.date_key = f.date_key JOIN dw.dim_customer c ON c.customer_key = f.customer_key JOIN dw.dim_product p ON p.product_key = f.product_key JOIN dw.dim_retailer r ON r.retailer_key = f.retailer_key;"
```

8. Trace a Gold fact back to its Silver and Bronze rows:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT f.order_id, s.silver_id, b.bronze_id, b.mongo_id, b.payload FROM dw.fact_sales f JOIN silver.orders_clean s ON s.silver_id = f.silver_id JOIN bronze.orders_raw b ON b.bronze_id = s.bronze_id WHERE f.order_id LIKE 'OLIST-%' ORDER BY f.loaded_at DESC LIMIT 1;"
```

9. Review data quality checks for the latest batch:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT layer, check_name, status, severity, checked_count, failed_count, details FROM dq.check_results WHERE batch_id = (SELECT batch_id FROM etl.batch_run ORDER BY started_at DESC LIMIT 1) ORDER BY layer, check_name;"
```

## Files

- `docker-compose.yml`: starts MongoDB, PostgreSQL, the dashboard, the ETL runner, and the Dockerized Olist pipeline.
- `init.sql`: creates the Bronze/Silver/Gold tables, audit and DQ tables, and indexes in PostgreSQL.
- `mongo-init.js`: creates the MongoDB raw collection and indexes; Olist data is imported explicitly.
- `Dockerfile`: builds the ETL runner image.
- `dashboard/app.py`: serves the lightweight browser dashboard from PostgreSQL.
- `etl/main_etl.py`: Docker entrypoint for the layered ETL.
- `etl/etl_legacy.py`: extracts raw MongoDB documents into Bronze, validates them into Silver, runs DQ, and loads the Gold star schema.
- `etl/dq.py`: runs per-batch data quality checks and reconciliation.
- `etl/import_olist_to_mongo.py`: converts Docker-downloaded Olist public CSV files into MongoDB raw order documents without bypassing Bronze/Silver/Gold.

## Notes

- The warehouse uses surrogate keys for dimensions and keeps `order_id` as the fact table business key.
- `date_key` is stored as `YYYYMMDD`, which is common in star schemas.
- `dw` is the Gold layer name in this starter project.
- Olist is the canonical source dataset for this project.
- Schema changes in `init.sql` apply automatically to a fresh PostgreSQL volume. If you already started the old stack or want a clean reset, run `docker compose down -v` and start again.
=======
Kiểm tra số dòng trong fact:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT order_id, quantity, price, discount, tax, batch_id, silver_id FROM dw.fact_sales ORDER BY loaded_at DESC LIMIT 20;"
```

Xem kết quả data quality của batch gần nhất:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT layer, check_name, status, severity, checked_count, failed_count, details FROM dq.check_results WHERE batch_id = (SELECT batch_id FROM etl.batch_run ORDER BY started_at DESC LIMIT 1) ORDER BY layer, check_name;"
```

## 7. Các file quan trọng

- `docker-compose.yml`: định nghĩa toàn bộ stack, mount đúng file trong `core/` và chạy các service bằng module `core.*`.
- `core/Dockerfile`: image dùng chung cho dashboard, ETL và pipeline import.
- `core/dashboard/app.py`: ứng dụng dashboard.
- `core/etl/main_etl.py`: entrypoint ETL.
- `core/etl/etl_legacy.py`: luồng Bronze/Silver/Gold chính.
- `core/etl/load.py`: load Gold và SCD2.
- `core/etl/import_olist_to_mongo.py`: import Olist CSV vào MongoDB.
- `core/etl/dq.py`: kiểm tra chất lượng dữ liệu.
- `core/etl/extract.py`, `core/etl/transform.py`, `core/etl/utils.py`: các helper ETL.
- `core/db/init.sql`: schema bootstrap cho PostgreSQL volume mới.
- `core/db/migration/*.sql`: migration cho schema và bảng liên quan.
- `core/db/tests/scd2_dim_customer_checks.sql`: kiểm tra hồi quy cho SCD2.
- `core/mongo-init.js`: script khởi tạo MongoDB.

## 8. Ghi chú vận hành

- Mã nguồn chuẩn của dự án nằm trong `core/`.
- `docker compose` đọc `.env` ở thư mục gốc và đồng thời truyền biến vào container qua `env_file`.
- `core/db/init.sql` và `core/mongo-init.js` chỉ chạy khi volume còn trống.
- `date_key` được lưu theo định dạng `YYYYMMDD`, phù hợp với star schema.
- `order_id` là business key của fact table.
- `dw` là tên lớp Gold trong dự án này.
- Olist là dataset nguồn chuẩn cho các lần chạy thường lệ.

## 9. Khắc phục sự cố

Nếu gặp lỗi `ModuleNotFoundError`:

- kiểm tra `docker-compose.yml` đang trỏ tới `core/Dockerfile`
- kiểm tra command của dashboard là `python -m core.dashboard.app`
- kiểm tra ETL entrypoint là `python -m core.etl.main_etl`

Nếu gặp lỗi thiếu dữ liệu CSV:

- bảo đảm các file Olist nằm đúng trong `data/olist/raw/`

Nếu muốn chạy lại từ đầu với schema mới:

```powershell
docker compose down -v
```

>>>>>>> theirs
