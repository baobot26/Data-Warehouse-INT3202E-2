# Data-Warehouse-INT3202E-2

This repository now includes a runnable starter deployment for the star schema in `Star Schema.drawio`.

Prerequisite:
- Docker Desktop or another Docker Engine must be running before you start the stack.

Architecture:
- `MongoDB` is the landing zone for raw order documents.
- `PostgreSQL` is the dimensional warehouse that implements the star schema.
- A small Dockerized ETL job reads from MongoDB and upserts data into the warehouse.

## Schema mapping

The Draw.io file maps to these warehouse tables in PostgreSQL:
- `dw.fact_sales`
- `dw.dim_customer`
- `dw.dim_product`
- `dw.dim_retailer`
- `dw.dim_address`
- `dw.dim_payment`
- `dw.dim_date`

## Start the stack

1. Start PostgreSQL and MongoDB:

```powershell
docker compose up -d postgres mongodb
```

2. Run the ETL job to load sample landing data from MongoDB into PostgreSQL:

```powershell
docker compose run --rm etl
```

3. Check the warehouse:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT order_id, quantity, price, discount, tax FROM dw.fact_sales;"
```

4. Inspect dimensions with a simple join:

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT f.order_id, d.full_date, c.customer_name, p.product_name, r.retailer_name FROM dw.fact_sales f JOIN dw.dim_date d ON d.date_key = f.date_key JOIN dw.dim_customer c ON c.customer_key = f.customer_key JOIN dw.dim_product p ON p.product_key = f.product_key JOIN dw.dim_retailer r ON r.retailer_key = f.retailer_key;"
```

## Files

- `docker-compose.yml`: starts MongoDB, PostgreSQL, and the ETL runner.
- `init.sql`: creates the star-schema tables and indexes in PostgreSQL.
- `mongo-init.js`: seeds raw order documents in MongoDB.
- `Dockerfile`: builds the ETL runner image.
- `etl/load_sample.py`: transforms raw MongoDB documents into warehouse dimensions and facts.

## Notes

- The warehouse uses surrogate keys for dimensions and keeps `order_id` as the fact table business key.
- `date_key` is stored as `YYYYMMDD`, which is common in star schemas.
- If you want a clean reset, run `docker compose down -v` and start again.
