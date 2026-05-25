#pagebreak()

#heading(level: 1, numbering: none, outlined: true)[Phụ lục A - Hướng dẫn triển khai hệ thống và kiểm tra kết quả chạy]

Phụ lục này trình bày cách chạy hệ thống theo cấu trúc repo hiện tại. Sau khi refactor, mã nguồn chính của project nằm trong thư mục `core/`; các service Docker chạy module `core.*` thay vì các module cũ ở root.

=== A.1 Các yêu cầu trước khi chạy hệ thống

#set par(first-line-indent: 0pt)

Docker Desktop hoặc Docker Engine cần đang chạy trước khi khởi động stack.

Tạo file `.env` ở thư mục gốc từ `.env.example`:

#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("Copy-Item .env.example .env", lang: "powershell")
)

Nếu dùng Bash:

#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("cp .env.example .env", lang: "bash")
)

Bộ dữ liệu Olist phải có sẵn trong `data/olist/raw/`. Pipeline hiện tại yêu cầu tối thiểu các file sau:

#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("data/olist/raw/olist_orders_dataset.csv
data/olist/raw/olist_order_items_dataset.csv
data/olist/raw/olist_customers_dataset.csv
data/olist/raw/olist_products_dataset.csv
data/olist/raw/olist_sellers_dataset.csv
data/olist/raw/olist_order_payments_dataset.csv
data/olist/raw/product_category_name_translation.csv", lang: "text")
)

Repo hiện cũng có `olist_geolocation_dataset.csv` và `olist_order_reviews_dataset.csv`, nhưng hai file này chưa được pipeline ETL chính sử dụng trực tiếp.

=== A.2 Reset dữ liệu khi cần chạy lại từ đầu

Khi thay đổi schema, thay đổi dataset hoặc muốn chạy lại từ môi trường sạch, xóa các volume cũ:

#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("docker compose down -v", lang: "powershell")
)

Lệnh này xóa dữ liệu cũ trong PostgreSQL và MongoDB volume, vì vậy chỉ dùng khi cần reset toàn bộ môi trường.

=== A.3 Khởi động các service nền

Khởi động PostgreSQL, MongoDB và dashboard:

#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("docker compose up -d postgres mongodb dashboard", lang: "powershell")
)

Trong cấu hình hiện tại:

- PostgreSQL dùng image `postgres:16-alpine` và mount schema bootstrap từ `core/db/init.sql`.
- MongoDB dùng image `mongo:7.0` và mount script bootstrap từ `core/mongo-init.js`.
- Dashboard chạy lệnh `python -m core.dashboard.app` và mở tại cổng `8501`.

=== A.4 Chạy pipeline đầy đủ từ Olist CSV đến Data Warehouse

Đây là cách chạy chính nên dùng cho báo cáo. Service `olist-pipeline` kiểm tra CSV Olist, import dữ liệu vào MongoDB, sau đó chạy ETL sang PostgreSQL.

#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("docker compose --profile tools run --rm olist-pipeline", lang: "powershell")
)

Trong container, service này thực thi lần lượt:

#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("python -m core.etl.import_olist_to_mongo --source-dir /data/olist/raw --limit \"$${OLIST_LIMIT:-0}\" --reset-prefix
python -m core.etl.main_etl", lang: "bash")
)

Ý nghĩa:

- `core.etl.import_olist_to_mongo` đọc CSV Olist, lọc đơn hàng `delivered`, chuyển mỗi order item thành document và upsert vào MongoDB `landing.orders_raw`.
- `core.etl.main_etl` chạy pipeline ETL từ MongoDB sang Bronze, Silver, Gold, Data Quality và audit.

=== A.5 Chạy thử nhanh với giới hạn dữ liệu

Khi chỉ muốn smoke test hoặc debug nhanh, đặt `OLIST_LIMIT` để import một số lượng bản ghi nhỏ.

PowerShell:

#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("$env:OLIST_LIMIT = 100
docker compose --profile tools run --rm olist-pipeline
Remove-Item Env:OLIST_LIMIT", lang: "powershell")
)

Bash:

#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("OLIST_LIMIT=100 docker compose --profile tools run --rm olist-pipeline", lang: "bash")
)

Nếu `OLIST_LIMIT=0` hoặc để trống, pipeline sẽ chạy toàn bộ dữ liệu Olist hợp lệ.

=== A.6 Chạy lại riêng ETL khi MongoDB đã có dữ liệu

Nếu MongoDB đã có dữ liệu trong `landing.orders_raw` và không cần import lại CSV, chạy riêng service ETL:

#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("docker compose run --rm etl", lang: "powershell")
)

Lệnh này dùng image build từ `core/Dockerfile` và chạy entrypoint mặc định:

#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("python -m core.etl.main_etl", lang: "bash")
)

=== A.7 Kiểm tra dashboard

Sau khi chạy pipeline, mở dashboard tại:

#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("http://localhost:8501", lang: "text")
)

Dashboard hiển thị các nhóm thông tin chính:

- số liệu Gold trong `dw.fact_sales`;
- trạng thái batch ETL gần nhất trong `etl.batch_run`;
- kết quả Data Quality trong `dq.check_results`;
- doanh thu theo ngày;
- top sản phẩm;
- các đơn hàng gần nhất.

=== A.8 Kiểm tra batch mới nhất

#set par(justify: false)
#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("docker compose exec postgres psql -U warehouse -d warehouse -c \"SELECT status, extracted_count, silver_accepted_count, silver_rejected_count, gold_loaded_count, finished_at - started_at AS elapsed FROM etl.batch_run ORDER BY started_at DESC LIMIT 1;\"", lang: "powershell")
)
#set par(justify: true)

Kết quả cho biết pipeline chạy thành công hay thất bại, số dòng được trích xuất, số dòng hợp lệ ở Silver, số dòng bị loại và số dòng được nạp vào Gold.

=== A.9 Kiểm tra số dòng trong Gold fact

#set par(justify: false)
#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("docker compose exec postgres psql -U warehouse -d warehouse -c \"SELECT COUNT(*) AS fact_sales_rows FROM dw.fact_sales;\"", lang: "powershell")
)
#set par(justify: true)

Truy vấn này kiểm tra nhanh số dòng hiện có trong bảng `dw.fact_sales`.

=== A.10 Kiểm tra dữ liệu trong fact table

#set par(justify: false)
#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("docker compose exec postgres psql -U warehouse -d warehouse -c \"SELECT order_id, quantity, price, discount, tax, batch_id, silver_id FROM dw.fact_sales ORDER BY loaded_at DESC LIMIT 20;\"", lang: "powershell")
)
#set par(justify: true)

Truy vấn này xác nhận dữ liệu đã được nạp vào Gold layer và vẫn giữ thông tin lineage qua `batch_id` và `silver_id`.

=== A.11 Kiểm tra kết quả Data Quality

#set par(justify: false)
#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("docker compose exec postgres psql -U warehouse -d warehouse -c \"SELECT layer, check_name, status, severity, checked_count, failed_count, details FROM dq.check_results WHERE batch_id = (SELECT batch_id FROM etl.batch_run ORDER BY started_at DESC LIMIT 1) ORDER BY layer, check_name;\"", lang: "powershell")
)
#set par(justify: true)

Nếu các check quan trọng có trạng thái `passed`, dữ liệu sau ETL đạt yêu cầu cơ bản để phục vụ phân tích.

=== A.12 Kiểm tra lineage từ Gold về Bronze

#set par(justify: false)
#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw("docker compose exec postgres psql -U warehouse -d warehouse -c \"SELECT f.order_id, s.silver_id, b.bronze_id, b.mongo_id, b.payload FROM dw.fact_sales f JOIN silver.orders_clean s ON s.silver_id = f.silver_id JOIN bronze.orders_raw b ON b.bronze_id = s.bronze_id WHERE f.order_id LIKE 'OLIST-%' ORDER BY f.loaded_at DESC LIMIT 1;\"", lang: "powershell")
)
#set par(justify: true)

Truy vấn này phù hợp với dữ liệu Olist hiện tại vì `order_id` sau import có tiền tố `OLIST-`.

=== A.13 Ghi chú vận hành

- Source code chuẩn nằm trong `core/`.
- `docker-compose.yml` build image từ `core/Dockerfile`.
- Các command runtime dùng module `core.dashboard.*` và `core.etl.*`.
- Olist là nguồn dữ liệu chuẩn cho các lần chạy thông thường.
- Các script sinh dữ liệu synthetic cũ không còn nằm trong workflow hiện tại.
- Gold layer đã được tối ưu theo hướng xử lý theo lô, mặc định load theo batch 1000 dòng.
- Pipeline commit theo batch để tránh giữ transaction quá lâu; khi có lỗi sẽ rollback để giải phóng transaction.
- Log ETL dùng `flush=True` để hiển thị tiến độ sớm hơn trong container.
- Nếu gặp lỗi thiếu CSV, kiểm tra lại thư mục `data/olist/raw/`.
- Nếu gặp lỗi schema cũ, chạy `docker compose down -v` rồi chạy lại từ đầu.

#pagebreak()

#heading(level: 1, numbering: none, outlined: true)[Phụ lục B - Cấu trúc project trên branch main]

Phụ lục này mô tả cấu trúc repo theo trạng thái hiện tại. Điểm thay đổi quan trọng là phần code chính đã được gom vào thư mục `core/`; các thư mục source cũ ở root như `etl/` hoặc `dashboard/` không còn là nơi chứa code chính.

=== B.1 Cấu trúc thư mục project

#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  raw(
"Data-Warehouse-INT3202E-2/
├── .dockerignore
├── .env.example
├── .github/
│   └── workflows/
│       └── flyway-ci.yml
├── core/
│   ├── __init__.py
│   ├── Dockerfile
│   ├── mongo-init.js
│   ├── dashboard/
│   │   ├── __init__.py
│   │   └── app.py
│   ├── db/
│   │   ├── init.sql
│   │   ├── migration/
│   │   │   ├── V1__create_schema_and_dims.sql
│   │   │   ├── V2__create_facts_and_indexes.sql
│   │   │   ├── V3__create_audit_tables.sql
│   │   │   ├── V4__create_bronze_silver_gold_lineage_and_dq.sql
│   │   │   ├── V5__create_watermark_table.sql
│   │   │   └── V6__alter_dim_customer_scd2.sql
│   │   └── tests/
│   │       └── scd2_dim_customer_checks.sql
│   └── etl/
│       ├── __init__.py
│       ├── audit.py
│       ├── dq.py
│       ├── etl_legacy.py
│       ├── extract.py
│       ├── import_olist_to_mongo.py
│       ├── load.py
│       ├── main_etl.py
│       ├── transform.py
│       └── utils.py
├── data/
│   └── olist/
│       └── raw/
│           ├── olist_customers_dataset.csv
│           ├── olist_geolocation_dataset.csv
│           ├── olist_order_items_dataset.csv
│           ├── olist_order_payments_dataset.csv
│           ├── olist_order_reviews_dataset.csv
│           ├── olist_orders_dataset.csv
│           ├── olist_products_dataset.csv
│           ├── olist_sellers_dataset.csv
│           └── product_category_name_translation.csv
├── local-only/
│   └── data/
│       └── olist/
│           └── raw/
├── vibe_jobs/
│   └── daily_etl.yml
├── backup.sh
├── docker-compose.yml
├── LICENSE
├── README.md
├── requirements.txt
└── Star Schema.drawio", lang: "text")
)

=== B.2 Mô tả các file cấu hình và triển khai

#table(
  columns: (1.8fr, 3.2fr),
  stroke: 0.5pt,
  align: (col, row) => if row == 0 { center } else { left },
  fill: (col, row) => if row == 0 { luma(230) } else { white },
  table.header(
    [*File / thư mục*], [*Vai trò*]
  ),

  [`.env.example`], [File mẫu chứa biến môi trường cho PostgreSQL, MongoDB và `OLIST_LIMIT`. Khi chạy local, tạo `.env` từ file này.],
  [`docker-compose.yml`], [Định nghĩa các service `postgres`, `mongodb`, `etl`, `dashboard` và `olist-pipeline`; build image từ `core/Dockerfile`; mount dữ liệu Olist từ `data/`.],
  [`core/Dockerfile`], [Image Python dùng chung cho dashboard, ETL và Olist pipeline. Image cài dependency từ `requirements.txt`, copy `core/` vào container và đặt `PYTHONPATH=/app`.],
  [`requirements.txt`], [Liệt kê thư viện Python chính: `psycopg`, `pymongo`, `python-dotenv`, `pandas`.],
  [`core/mongo-init.js`], [Bootstrap MongoDB, tạo collection `landing.orders_raw` và index cần thiết. Dữ liệu Olist được import rõ ràng bằng pipeline, không seed ngẫu nhiên.],
  [`core/db/init.sql`], [Schema bootstrap cho PostgreSQL volume mới, tạo các schema/tables Bronze, Silver, Gold, ETL audit và DQ.],
  [`backup.sh`], [Script hỗ trợ backup thủ công.],
  [`README.md`], [Tài liệu nguồn hiện tại cho cách chạy stack, pipeline Olist, kiểm tra batch, fact table và DQ.],
  [`Star Schema.drawio`], [Sơ đồ thiết kế mô hình Star Schema của Gold layer.],
  [`data/olist/raw/`], [Bộ CSV Olist được dùng làm nguồn dữ liệu chuẩn cho pipeline hiện tại.],
  [`local-only/data/olist/raw/`], [Bản dữ liệu Olist dành cho nhu cầu local-only; không phải code xử lý chính.],
  [`vibe_jobs/daily_etl.yml`], [Cấu hình job ETL định kỳ thử nghiệm/định hướng orchestration.]
)

#align(center)[
  #text[Table B.1:] Mô tả các file cấu hình và triển khai hiện tại
]

=== B.3 Mô tả thư mục `core/`

`core/` là nơi chứa source code chính của project sau refactor. Các service trong Docker Compose đều chạy module từ package này.

#table(
  columns: (1.8fr, 3.2fr),
  stroke: 0.5pt,
  align: (col, row) => if row == 0 { center } else { left },
  fill: (col, row) => if row == 0 { luma(230) } else { white },
  table.header(
    [*Thành phần*], [*Vai trò*]
  ),

  [`core/dashboard/app.py`], [Dashboard web đọc dữ liệu từ PostgreSQL và hiển thị Gold metrics, latest batch, DQ results, top products và recent orders.],
  [`core/etl/main_etl.py`], [Entry point ETL, gọi `run_pipeline()` để chạy luồng xử lý.],
  [`core/etl/etl_legacy.py`], [Orchestration chính của pipeline: tạo batch, extract vào Bronze, transform sang Silver, load Gold, chạy DQ và cập nhật trạng thái batch.],
  [`core/etl/import_olist_to_mongo.py`], [Đọc CSV Olist, join dữ liệu, lọc `delivered`, tạo document và upsert vào MongoDB `landing.orders_raw`.],
  [`core/etl/load.py`], [Logic load Gold và xử lý SCD Type 2 cho `dw.dim_customer`.],
  [`core/etl/dq.py`], [Triển khai các kiểm tra Data Quality và reconciliation, lưu kết quả vào `dq.check_results`.],
  [`core/etl/extract.py`], [Helper trích xuất dữ liệu.],
  [`core/etl/transform.py`], [Helper chuẩn hóa và chuyển đổi dữ liệu.],
  [`core/etl/audit.py`], [Helper audit theo mô hình cũ/tiện ích liên quan đến ghi nhận job.],
  [`core/etl/utils.py`], [Các hàm tiện ích dùng chung, bao gồm kiểm tra biến môi trường.],
  [`core/db/init.sql`], [Schema bootstrap cho database mới.],
  [`core/db/migration/`], [Các migration SQL theo phiên bản.],
  [`core/db/tests/scd2_dim_customer_checks.sql`], [Truy vấn kiểm tra hồi quy cho SCD2 customer.]
)

#align(center)[
  #text[Table B.2:] Các thành phần chính trong `core/`
]

=== B.4 Mô tả thư mục migration

Thư mục `core/db/migration` chứa các file SQL quản lý thay đổi schema theo phiên bản.

#let migration-file(parts) = box(width: 100%)[
  #text(font: "DejaVu Sans Mono")[
    #for part in parts {
      raw(part, lang: "text")
      sym.zws
    }
  ]
]

#table(
  columns: (2.8fr, 3.2fr),
  stroke: 0.5pt,
  inset: 5pt,
  align: (col, row) => if row == 0 { center } else { left },
  fill: (col, row) => if row == 0 { luma(230) } else { white },

  table.header(
    [*Migration*], [*Vai trò*]
  ),

  [#migration-file(("V1__", "create_", "schema_", "and_", "dims.sql"))],
  [Tạo schema `dw` và các bảng dimension ban đầu.],

  [#migration-file(("V2__", "create_", "facts_", "and_", "indexes.sql"))],
  [Tạo bảng `dw.fact_sales` và các index hỗ trợ truy vấn phân tích.],

  [#migration-file(("V3__", "create_", "audit_", "tables.sql"))],
  [Bổ sung các bảng audit ETL theo mô hình ban đầu.],

  [#migration-file(("V4__", "create_", "bronze_", "silver_", "gold_", "lineage_", "and_", "dq.sql"))],
  [Bổ sung schema `etl`, `bronze`, `silver`, `dq`, bảng `etl.batch_run`, bảng Bronze/Silver, lineage và `dq.check_results`.],

  [#migration-file(("V5__", "create_", "watermark_", "table.sql"))],
  [Tạo bảng `etl_watermark` để chuẩn bị cho incremental loading/watermark.],

  [#migration-file(("V6__", "alter_", "dim_", "customer_", "scd2.sql"))],
  [Bổ sung `valid_from`, `valid_to`, `is_current`, unique index cho current customer và constraint hợp lệ cho SCD Type 2.]
)

#align(center)[
  #text[Table B.3:] Các file migration hiện tại
]

=== B.5 Mô tả dữ liệu Olist

Thư mục `data/olist/raw/` chứa dữ liệu nguồn Olist. Pipeline hiện tại sử dụng các file bắt buộc sau:

#table(
  columns: (2.5fr, 3fr),
  stroke: 0.5pt,
  align: (col, row) => if row == 0 { center } else { left },
  fill: (col, row) => if row == 0 { luma(230) } else { white },
  table.header(
    [*File*], [*Vai trò trong pipeline*]
  ),

  [`olist_orders_dataset.csv`], [Thông tin đơn hàng và trạng thái đơn hàng.],
  [`olist_order_items_dataset.csv`], [Chi tiết từng order item; đây là grain chính khi tạo document Olist.],
  [`olist_customers_dataset.csv`], [Thông tin khách hàng và địa chỉ khách hàng.],
  [`olist_products_dataset.csv`], [Thông tin sản phẩm.],
  [`olist_sellers_dataset.csv`], [Thông tin người bán/retailer.],
  [`olist_order_payments_dataset.csv`], [Thông tin phương thức thanh toán.],
  [`product_category_name_translation.csv`], [Dịch/chuẩn hóa tên danh mục sản phẩm.]
)

#align(center)[
  #text[Table B.4:] Các file Olist được pipeline sử dụng
]

Hai file `olist_geolocation_dataset.csv` và `olist_order_reviews_dataset.csv` có trong repo nhưng chưa được pipeline ETL chính sử dụng trực tiếp.

=== B.6 Mô tả workflow và job phụ trợ

#table(
  columns: (1.8fr, 3.2fr),
  stroke: 0.5pt,
  align: (col, row) => if row == 0 { center } else { left },
  fill: (col, row) => if row == 0 { luma(230) } else { white },
  table.header(
    [*File*], [*Vai trò*]
  ),

  [`.github/workflows/flyway-ci.yml`], [Workflow kiểm thử migration bằng Flyway trên GitHub Actions. Cần lưu ý khi bảo trì: source migration hiện nằm trong `core/db/migration`.],
  [`vibe_jobs/daily_etl.yml`], [Cấu hình job ETL định kỳ ở mức định hướng. File này mô tả lịch chạy hằng ngày và retry policy; nếu dùng thật cần đồng bộ command sang module hiện tại `core.etl.main_etl`. Runtime chính trong README vẫn là Docker Compose.]
)

#align(center)[
  #text[Table B.5:] Workflow và job phụ trợ
]

=== B.7 Luồng chạy chính của project

Luồng chạy thực tế theo README hiện tại có thể tóm tắt như sau:

#set par(justify: false)
#block(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
  [
    Olist CSV trong `data/olist/raw`
    $arrow.r$ `python -m core.etl.import_olist_to_mongo`
    $arrow.r$ MongoDB `landing.orders_raw`
    $arrow.r$ `python -m core.etl.main_etl`
    $arrow.r$ `etl.batch_run`
    $arrow.r$ `bronze.orders_raw`
    $arrow.r$ `silver.orders_clean` / `silver.orders_rejected`
    $arrow.r$ `dw.fact_sales` và các dimension
    $arrow.r$ `dq.check_results`
    $arrow.r$ dashboard `core.dashboard.app`
  ]
)
#set par(justify: true)

Cách tổ chức này giúp project có thể chạy lại bằng Docker Compose, giữ source code tập trung trong `core/`, đồng thời bảo toàn được các lớp dữ liệu Bronze, Silver, Gold, audit, Data Quality và lineage.
