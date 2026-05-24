# Data-Warehouse-INT3202E-2

This repository now includes a runnable starter deployment for the star schema in `Star Schema.drawio`.

Prerequisite:
- Docker Desktop or another Docker Engine must be running before you start the stack.
- Create a local `.env` file from `.env.example` before the first run:

```powershell
Copy-Item .env.example .env
```

Olist raw CSV files must be present in `data/olist/raw` before running the pipeline. The repository is expected to include these files for test runs:

```text
data/olist/raw/olist_orders_dataset.csv
data/olist/raw/olist_order_items_dataset.csv
data/olist/raw/olist_customers_dataset.csv
data/olist/raw/olist_products_dataset.csv
data/olist/raw/olist_sellers_dataset.csv
data/olist/raw/olist_order_payments_dataset.csv
data/olist/raw/product_category_name_translation.csv
```

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

1. Start from clean database volumes when switching to the Olist-only source.

```powershell
docker compose down -v
```

2. Start PostgreSQL, MongoDB, and the dashboard:

```powershell
docker compose up -d postgres mongodb dashboard
```

3. Import the checked-in Olist raw CSV files into MongoDB, and run the ETL:

```powershell
docker compose --profile tools run --rm olist-pipeline
```

The `olist-pipeline` service runs fully inside Docker:
- verifies the required Olist CSV files exist in `data/olist/raw`;
- imports delivered Olist order items into MongoDB `landing.orders_raw`;
- runs `python -m etl.main_etl` to load Bronze, Silver, Gold, DQ, and audit tables.

The importer keeps the existing pipeline intact by converting each Olist order item into one MongoDB raw order document with an `OLIST-` order id. Olist is the only supported source dataset for regular runs in this project. Set `OLIST_LIMIT` in `.env` to a positive number for a smaller test import.

For timing in PowerShell:

```powershell
Measure-Command { docker compose --profile tools run --rm olist-pipeline }
```

4. Rerun only the ETL when MongoDB already has raw Olist data:

```powershell
docker compose run --rm etl
```

5. Check the warehouse:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT order_id, quantity, price, discount, tax, batch_id, silver_id FROM dw.fact_sales ORDER BY loaded_at DESC LIMIT 20;"
```

Check the latest batch size and runtime:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT status, extracted_count, silver_accepted_count, silver_rejected_count, gold_loaded_count, finished_at - started_at AS elapsed FROM etl.batch_run ORDER BY started_at DESC LIMIT 1;"
```

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
