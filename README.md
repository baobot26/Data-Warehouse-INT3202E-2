# Data-Warehouse-INT3202E-2

Dockerized data warehouse starter for the star schema in `Star Schema.drawio`. The canonical source code now lives under `core/`.

## Prerequisites

- Docker Desktop or another Docker Engine must be running.
- Create a local `.env` file from `.env.example` before the first run.

PowerShell:

```powershell
Copy-Item .env.example .env
```

Bash:

```bash
cp .env.example .env
```

Olist raw CSV files must be present in `data/olist/raw/` before running the pipeline:

- `data/olist/raw/olist_orders_dataset.csv`
- `data/olist/raw/olist_order_items_dataset.csv`
- `data/olist/raw/olist_customers_dataset.csv`
- `data/olist/raw/olist_products_dataset.csv`
- `data/olist/raw/olist_sellers_dataset.csv`
- `data/olist/raw/olist_order_payments_dataset.csv`
- `data/olist/raw/product_category_name_translation.csv`

## Architecture

- MongoDB stores raw order documents in `landing.orders_raw`.
- PostgreSQL stores three layers:
  - bronze: append-only raw payloads with batch metadata
  - silver: typed clean/rejected order rows linked back to bronze
  - dw: the Gold star schema for analytics
- `core/dashboard/app.py` serves the browser dashboard.
- `etl.batch_run` records pipeline runs for audit and reprocessing.
- `dq.check_results` stores per-batch data quality checks and reconciliation results.

## Schema mapping

The Draw.io file maps to these warehouse tables in PostgreSQL:

- `dw.fact_sales`
- `dw.dim_customer`
- `dw.dim_product`
- `dw.dim_retailer`
- `dw.dim_address`
- `dw.dim_payment`
- `dw.dim_date`

Layering and audit tables:

- `etl.batch_run`
- `bronze.orders_raw`
- `silver.orders_clean`
- `silver.orders_rejected`
- `dq.check_results`

## Start the stack

1. Reset volumes when you need a clean database.

```powershell
docker compose down -v
```

2. Start the base services.

```powershell
docker compose up -d postgres mongodb dashboard
```

3. Run the pipeline using one of the three modes below.

### Cách 1 (Full)

Run the full Olist pipeline, importing the checked-in CSV files into MongoDB and then executing the ETL.

```powershell
docker compose --profile tools run --rm olist-pipeline
```

This path runs `python -m core.etl.import_olist_to_mongo` and then `python -m core.etl.main_etl` inside Docker.

### Cách 2 (Test nhanh / Giới hạn)

Limit the import size with `OLIST_LIMIT`.

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

Use this mode for smoke tests, faster iteration, or CI-style checks.

### Cách 3 (Rerun ETL)

Rerun only the ETL when MongoDB already contains raw Olist data.

```powershell
docker compose run --rm etl
```

This container runs `python -m core.etl.main_etl` against the existing MongoDB landing data.

## Verify

Open `http://localhost:8501` to view Gold sales metrics, the latest ETL batch status, recent data quality results, top products, and recent orders.

Check the latest batch summary:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT status, extracted_count, silver_accepted_count, silver_rejected_count, gold_loaded_count, finished_at - started_at AS elapsed FROM etl.batch_run ORDER BY started_at DESC LIMIT 1;"
```

Inspect the latest Gold facts:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT order_id, quantity, price, discount, tax, batch_id, silver_id FROM dw.fact_sales ORDER BY loaded_at DESC LIMIT 20;"
```

Review data quality checks for the latest batch:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT layer, check_name, status, severity, checked_count, failed_count, details FROM dq.check_results WHERE batch_id = (SELECT batch_id FROM etl.batch_run ORDER BY started_at DESC LIMIT 1) ORDER BY layer, check_name;"
```

## Files

- `docker-compose.yml`: starts PostgreSQL, MongoDB, the dashboard, the ETL runner, and the Dockerized Olist pipeline.
- `core/Dockerfile`: builds the shared runtime image and runs `python -m core.etl.main_etl`.
- `core/dashboard/app.py`: dashboard entrypoint.
- `core/etl/main_etl.py`: ETL entrypoint.
- `core/etl/etl_legacy.py`: layered Bronze/Silver/Gold pipeline orchestration.
- `core/etl/import_olist_to_mongo.py`: imports Olist CSV files into MongoDB.
- `core/etl/load.py`: SCD2 and Gold load logic.
- `core/etl/dq.py`: data quality checks and reconciliation.
- `core/etl/extract.py`, `core/etl/transform.py`, `core/etl/utils.py`: supporting ETL helpers.
- `core/db/init.sql`: bootstrap schema for a fresh PostgreSQL volume.
- `core/db/migration/*.sql`: schema migration scripts.
- `core/db/tests/scd2_dim_customer_checks.sql`: SCD2 regression checks.
- `core/mongo-init.js`: MongoDB bootstrap script.

## Notes

- The warehouse uses surrogate keys for dimensions and keeps `order_id` as the fact table business key.
- `date_key` is stored as `YYYYMMDD`, which is common in star schemas.
- `dw` is the Gold layer name in this starter project.
- Olist is the canonical source dataset for regular runs.
- Schema changes in `core/db/init.sql` apply automatically to a fresh PostgreSQL volume. If you need a clean reset, run `docker compose down -v` and start again.
