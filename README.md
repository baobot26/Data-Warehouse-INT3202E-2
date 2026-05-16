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

1. Start PostgreSQL and MongoDB:

```powershell
docker compose up -d postgres mongodb
```

2. Optional for scale testing: generate a larger deterministic MongoDB source set.

```powershell
docker compose build etl
docker compose run --rm --entrypoint python etl -m etl.seed_scale_data --count 100000 --reset
```

This keeps the repository small while letting you seed 10,000, 100,000, or more synthetic orders for performance testing. The `--reset` flag removes previously generated `ORD-SCALE-` records before inserting the requested volume.

3. Run the ETL job to load sample landing data from MongoDB into PostgreSQL:

```powershell
docker compose run --rm etl
```

For scale-test timing in PowerShell:

```powershell
Measure-Command { docker compose run --rm etl }
```

4. Check the warehouse:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT order_id, quantity, price, discount, tax, batch_id, silver_id FROM dw.fact_sales;"
```

Check the latest batch size and runtime:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT status, extracted_count, silver_accepted_count, silver_rejected_count, gold_loaded_count, finished_at - started_at AS elapsed FROM etl.batch_run ORDER BY started_at DESC LIMIT 1;"
```

5. Inspect dimensions with a simple join:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT f.order_id, d.full_date, c.customer_name, p.product_name, r.retailer_name FROM dw.fact_sales f JOIN dw.dim_date d ON d.date_key = f.date_key JOIN dw.dim_customer c ON c.customer_key = f.customer_key JOIN dw.dim_product p ON p.product_key = f.product_key JOIN dw.dim_retailer r ON r.retailer_key = f.retailer_key;"
```

6. Trace a Gold fact back to its Silver and Bronze rows:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT f.order_id, s.silver_id, b.bronze_id, b.mongo_id, b.payload FROM dw.fact_sales f JOIN silver.orders_clean s ON s.silver_id = f.silver_id JOIN bronze.orders_raw b ON b.bronze_id = s.bronze_id WHERE f.order_id = 'ORD-1001';"
```

7. Review data quality checks for the latest batch:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT layer, check_name, status, severity, checked_count, failed_count, details FROM dq.check_results WHERE batch_id = (SELECT batch_id FROM etl.batch_run ORDER BY started_at DESC LIMIT 1) ORDER BY layer, check_name;"
```

## Files

- `docker-compose.yml`: starts MongoDB, PostgreSQL, and the ETL runner.
- `init.sql`: creates the Bronze/Silver/Gold tables, audit and DQ tables, and indexes in PostgreSQL.
- `mongo-init.js`: seeds raw order documents in MongoDB.
- `Dockerfile`: builds the ETL runner image.
- `etl/main_etl.py`: Docker entrypoint for the layered ETL.
- `etl/etl_legacy.py`: extracts raw MongoDB documents into Bronze, validates them into Silver, runs DQ, and loads the Gold star schema.
- `etl/dq.py`: runs per-batch data quality checks and reconciliation.
- `etl/seed_scale_data.py`: generates deterministic synthetic MongoDB orders for scale testing.

## Notes

- The warehouse uses surrogate keys for dimensions and keeps `order_id` as the fact table business key.
- `date_key` is stored as `YYYYMMDD`, which is common in star schemas.
- `dw` is the Gold layer name in this starter project.
- Schema changes in `init.sql` apply automatically to a fresh PostgreSQL volume. If you already started the old stack or want a clean reset, run `docker compose down -v` and start again.
