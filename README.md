# Data-Warehouse-INT3202E-2

This repository now includes a runnable starter deployment for the star schema in `Star Schema.drawio`.

Prerequisite:
- Docker Desktop or another Docker Engine must be running before you start the stack.
- Create a local `.env` file from `.env.example` before the first run:

```powershell
Copy-Item .env.example .env
```

Architecture:
- `MongoDB` is the source system for raw order documents.
- `PostgreSQL` stores three data layers:
  - `bronze`: append-only raw MongoDB payloads with batch metadata.
  - `silver`: typed clean/rejected order rows linked back to bronze.
  - `dw`: the Gold star schema used for analytics.
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

2. Start PostgreSQL and MongoDB:

```powershell
docker compose up -d postgres mongodb
```

3. Import Olist CSV files into MongoDB raw landing.

Download the Olist CSV files into `data/olist/raw` with their original filenames:

```text
data/olist/raw/olist_orders_dataset.csv
data/olist/raw/olist_order_items_dataset.csv
data/olist/raw/olist_customers_dataset.csv
data/olist/raw/olist_products_dataset.csv
data/olist/raw/olist_sellers_dataset.csv
data/olist/raw/olist_order_payments_dataset.csv
data/olist/raw/product_category_name_translation.csv
```

Validate the conversion without writing to MongoDB:

```powershell
docker compose run --rm --entrypoint python etl -m etl.import_olist_to_mongo --source-dir /data/olist/raw --limit 10 --dry-run
```

Import delivered Olist order items into `landing.orders_raw`:

```powershell
docker compose run --rm --entrypoint python etl -m etl.import_olist_to_mongo --source-dir /data/olist/raw --reset-prefix
```

The importer keeps the existing pipeline intact by converting each Olist order item into one MongoDB raw order document with an `OLIST-` order id. Olist is the only supported source dataset for regular runs in this project.

4. Run the ETL job to load imported Olist landing data from MongoDB into PostgreSQL:

```powershell
docker compose run --rm etl
```

For timing in PowerShell:

```powershell
Measure-Command { docker compose run --rm etl }
```

5. Check the warehouse:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT order_id, quantity, price, discount, tax, batch_id, silver_id FROM dw.fact_sales ORDER BY loaded_at DESC LIMIT 20;"
```

Check the latest batch size and runtime:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT status, extracted_count, silver_accepted_count, silver_rejected_count, gold_loaded_count, finished_at - started_at AS elapsed FROM etl.batch_run ORDER BY started_at DESC LIMIT 1;"
```

6. Inspect dimensions with a simple join:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT f.order_id, d.full_date, c.customer_name, p.product_name, r.retailer_name FROM dw.fact_sales f JOIN dw.dim_date d ON d.date_key = f.date_key JOIN dw.dim_customer c ON c.customer_key = f.customer_key JOIN dw.dim_product p ON p.product_key = f.product_key JOIN dw.dim_retailer r ON r.retailer_key = f.retailer_key;"
```

7. Trace a Gold fact back to its Silver and Bronze rows:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT f.order_id, s.silver_id, b.bronze_id, b.mongo_id, b.payload FROM dw.fact_sales f JOIN silver.orders_clean s ON s.silver_id = f.silver_id JOIN bronze.orders_raw b ON b.bronze_id = s.bronze_id WHERE f.order_id LIKE 'OLIST-%' ORDER BY f.loaded_at DESC LIMIT 1;"
```

8. Review data quality checks for the latest batch:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT layer, check_name, status, severity, checked_count, failed_count, details FROM dq.check_results WHERE batch_id = (SELECT batch_id FROM etl.batch_run ORDER BY started_at DESC LIMIT 1) ORDER BY layer, check_name;"
```

## Files

- `docker-compose.yml`: starts MongoDB, PostgreSQL, and the ETL runner.
- `init.sql`: creates the Bronze/Silver/Gold tables, audit and DQ tables, and indexes in PostgreSQL.
- `mongo-init.js`: creates the MongoDB raw collection and indexes; Olist data is imported explicitly.
- `Dockerfile`: builds the ETL runner image.
- `etl/main_etl.py`: Docker entrypoint for the layered ETL.
- `etl/etl_legacy.py`: extracts raw MongoDB documents into Bronze, validates them into Silver, runs DQ, and loads the Gold star schema.
- `etl/dq.py`: runs per-batch data quality checks and reconciliation.
- `etl/import_olist_to_mongo.py`: converts Olist public CSV files into MongoDB raw order documents without bypassing Bronze/Silver/Gold.

## Notes

- The warehouse uses surrogate keys for dimensions and keeps `order_id` as the fact table business key.
- `date_key` is stored as `YYYYMMDD`, which is common in star schemas.
- `dw` is the Gold layer name in this starter project.
- Olist is the canonical source dataset for this project.
- Schema changes in `init.sql` apply automatically to a fresh PostgreSQL volume. If you already started the old stack or want a clean reset, run `docker compose down -v` and start again.
