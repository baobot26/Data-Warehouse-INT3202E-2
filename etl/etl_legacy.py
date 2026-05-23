import hashlib
import json
import os
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pymongo import MongoClient
from psycopg import connect

from etl.dq import run_data_quality_checks


PIPELINE_NAME = "orders"


def to_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return to_decimal(value)


def normalize_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError(f"Unsupported timestamp value: {value!r}")


def json_payload(doc: dict[str, Any]) -> str:
    payload = dict(doc)
    if "_id" in payload:
        payload["_id"] = str(payload["_id"])
    return json.dumps(payload, default=str, sort_keys=True)


def payload_hash(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def reject(reason: str) -> tuple[None, str]:
    return None, reason


def clean_order_payload(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(payload, dict):
        return reject("payload must be a JSON object")

    try:
        raw_order_id = payload.get("order_id")
        if raw_order_id is None:
            return reject("missing order_id")
        order_id = str(raw_order_id).strip()
        if not order_id:
            return reject("missing order_id")

        sold_at = normalize_timestamp(payload["sold_at"])
        quantity = int(payload["quantity"])
        price = to_decimal(payload["price"])
        discount = to_decimal(payload.get("discount", 0))
        tax = to_decimal(payload.get("tax", 0))
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        return reject(f"invalid order fields: {exc}")

    if quantity <= 0:
        return reject("quantity must be greater than 0")
    if price < 0:
        return reject("price must be greater than or equal to 0")
    if discount < 0 or tax < 0:
        return reject("discount and tax must be greater than or equal to 0")

    for nested_key in ("customer", "product", "retailer", "address", "payment"):
        if not isinstance(payload.get(nested_key), dict):
            return reject(f"missing or invalid {nested_key}")

    customer = payload["customer"]
    product = payload["product"]
    retailer = payload["retailer"]
    address = payload["address"]
    payment = payload["payment"]

    required_values = {
        "customer_id": customer.get("customer_id"),
        "customer_name": customer.get("customer_name"),
        "product_id": product.get("product_id"),
        "product_name": product.get("product_name"),
        "retailer_id": retailer.get("retailer_id"),
        "retailer_name": retailer.get("retailer_name"),
        "street": address.get("street"),
        "commune_ward": address.get("commune_ward"),
        "province_city": address.get("province_city"),
        "payment_type": payment.get("payment_type"),
        "method_provider": payment.get("method_provider"),
    }
    missing = [name for name, value in required_values.items() if not value]
    if missing:
        return reject(f"missing required field(s): {', '.join(missing)}")

    try:
        quantity_in_stock = optional_int(product.get("quantity_in_stock"))
        retailer_rating = optional_decimal(retailer.get("rating"))
    except (TypeError, ValueError, InvalidOperation) as exc:
        return reject(f"invalid optional field: {exc}")

    return (
        {
            "order_id": order_id,
            "sold_at": sold_at,
            "quantity": quantity,
            "price": price,
            "discount": discount,
            "tax": tax,
            "customer_id": str(customer["customer_id"]),
            "customer_name": str(customer["customer_name"]),
            "customer_phone_number": customer.get("phone_number"),
            "customer_email": customer.get("email"),
            "customer_membership": customer.get("membership"),
            "product_id": str(product["product_id"]),
            "product_name": str(product["product_name"]),
            "product_category": product.get("product_category"),
            "product_brand": product.get("product_brand"),
            "quantity_in_stock": quantity_in_stock,
            "retailer_id": str(retailer["retailer_id"]),
            "retailer_name": str(retailer["retailer_name"]),
            "retailer_phone_number": retailer.get("phone_number"),
            "retailer_email": retailer.get("email"),
            "retailer_rating": retailer_rating,
            "street": str(address["street"]),
            "commune_ward": str(address["commune_ward"]),
            "province_city": str(address["province_city"]),
            "payment_type": str(payment["payment_type"]),
            "method_provider": str(payment["method_provider"]),
        },
        "",
    )


def pg_connect():
    return connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        dbname=os.getenv("PGDATABASE") or os.getenv("POSTGRES_DB", "warehouse"),
        user=os.getenv("PGUSER") or os.getenv("POSTGRES_USER", "warehouse"),
        password=os.getenv("PGPASSWORD") or os.getenv("POSTGRES_PASSWORD", "warehouse"),
    )


def start_batch(cur, batch_id: uuid.UUID, mongo_db_name: str, collection_name: str) -> None:
    cur.execute(
        """
        INSERT INTO etl.batch_run (
            batch_id,
            pipeline_name,
            source_database,
            source_collection,
            status
        )
        VALUES (%s, %s, %s, %s, 'running');
        """,
        (batch_id, PIPELINE_NAME, mongo_db_name, collection_name),
    )


def update_batch_failure(pg_conn, batch_id: uuid.UUID, error: Exception) -> None:
    pg_conn.rollback()
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE etl.batch_run
            SET status = 'failed',
                finished_at = NOW(),
                error_message = %s
            WHERE batch_id = %s;
            """,
            (str(error)[:2000], batch_id),
        )
    pg_conn.commit()


def extract_bronze(cur, batch_id: uuid.UUID, collection, collection_name: str) -> int:
    extracted = 0
    for doc in collection.find():
        payload_json = json_payload(doc)
        mongo_id = str(doc.get("_id", ""))
        cur.execute(
            """
            INSERT INTO bronze.orders_raw (
                batch_id,
                mongo_id,
                source_collection,
                payload,
                payload_hash
            )
            VALUES (%s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (batch_id, mongo_id) DO UPDATE
            SET payload = EXCLUDED.payload,
                payload_hash = EXCLUDED.payload_hash,
                extracted_at = NOW();
            """,
            (
                batch_id,
                mongo_id,
                collection_name,
                payload_json,
                payload_hash(payload_json),
            ),
        )
        extracted += 1

    cur.execute(
        """
        UPDATE etl.batch_run
        SET bronze_completed_at = NOW(),
            extracted_count = %s
        WHERE batch_id = %s;
        """,
        (extracted, batch_id),
    )
    return extracted


def insert_clean_order(cur, bronze_row: dict[str, Any], clean: dict[str, Any]) -> int:
    cur.execute(
        """
        INSERT INTO silver.orders_clean (
            bronze_id,
            batch_id,
            mongo_id,
            payload_hash,
            order_id,
            sold_at,
            quantity,
            price,
            discount,
            tax,
            customer_id,
            customer_name,
            customer_phone_number,
            customer_email,
            customer_membership,
            product_id,
            product_name,
            product_category,
            product_brand,
            quantity_in_stock,
            retailer_id,
            retailer_name,
            retailer_phone_number,
            retailer_email,
            retailer_rating,
            street,
            commune_ward,
            province_city,
            payment_type,
            method_provider
        )
        VALUES (
            %(bronze_id)s,
            %(batch_id)s,
            %(mongo_id)s,
            %(payload_hash)s,
            %(order_id)s,
            %(sold_at)s,
            %(quantity)s,
            %(price)s,
            %(discount)s,
            %(tax)s,
            %(customer_id)s,
            %(customer_name)s,
            %(customer_phone_number)s,
            %(customer_email)s,
            %(customer_membership)s,
            %(product_id)s,
            %(product_name)s,
            %(product_category)s,
            %(product_brand)s,
            %(quantity_in_stock)s,
            %(retailer_id)s,
            %(retailer_name)s,
            %(retailer_phone_number)s,
            %(retailer_email)s,
            %(retailer_rating)s,
            %(street)s,
            %(commune_ward)s,
            %(province_city)s,
            %(payment_type)s,
            %(method_provider)s
        )
        ON CONFLICT (bronze_id) DO UPDATE
        SET batch_id = EXCLUDED.batch_id,
            mongo_id = EXCLUDED.mongo_id,
            payload_hash = EXCLUDED.payload_hash,
            order_id = EXCLUDED.order_id,
            sold_at = EXCLUDED.sold_at,
            quantity = EXCLUDED.quantity,
            price = EXCLUDED.price,
            discount = EXCLUDED.discount,
            tax = EXCLUDED.tax,
            customer_id = EXCLUDED.customer_id,
            customer_name = EXCLUDED.customer_name,
            customer_phone_number = EXCLUDED.customer_phone_number,
            customer_email = EXCLUDED.customer_email,
            customer_membership = EXCLUDED.customer_membership,
            product_id = EXCLUDED.product_id,
            product_name = EXCLUDED.product_name,
            product_category = EXCLUDED.product_category,
            product_brand = EXCLUDED.product_brand,
            quantity_in_stock = EXCLUDED.quantity_in_stock,
            retailer_id = EXCLUDED.retailer_id,
            retailer_name = EXCLUDED.retailer_name,
            retailer_phone_number = EXCLUDED.retailer_phone_number,
            retailer_email = EXCLUDED.retailer_email,
            retailer_rating = EXCLUDED.retailer_rating,
            street = EXCLUDED.street,
            commune_ward = EXCLUDED.commune_ward,
            province_city = EXCLUDED.province_city,
            payment_type = EXCLUDED.payment_type,
            method_provider = EXCLUDED.method_provider,
            cleaned_at = NOW()
        RETURNING silver_id;
        """,
        {
            **bronze_row,
            **clean,
        },
    )
    return cur.fetchone()[0]


def insert_rejected_order(cur, bronze_row: dict[str, Any], reason: str) -> None:
    payload = bronze_row["payload"]
    order_id = payload.get("order_id") if isinstance(payload, dict) else None
    cur.execute(
        """
        INSERT INTO silver.orders_rejected (
            bronze_id,
            batch_id,
            mongo_id,
            order_id,
            reject_reason
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (bronze_id) DO UPDATE
        SET order_id = EXCLUDED.order_id,
            reject_reason = EXCLUDED.reject_reason,
            rejected_at = NOW();
        """,
        (
            bronze_row["bronze_id"],
            bronze_row["batch_id"],
            bronze_row["mongo_id"],
            str(order_id) if order_id else None,
            reason,
        ),
    )


def load_silver(cur, batch_id: uuid.UUID) -> tuple[int, int]:
    cur.execute(
        """
        SELECT bronze_id, batch_id, mongo_id, payload, payload_hash
        FROM bronze.orders_raw
        WHERE batch_id = %s
        ORDER BY bronze_id;
        """,
        (batch_id,),
    )
    rows = cur.fetchall()
    colnames = [desc.name for desc in cur.description]

    accepted = 0
    rejected = 0
    for row in rows:
        bronze_row = dict(zip(colnames, row))
        clean, reason = clean_order_payload(bronze_row["payload"])
        if clean is None:
            insert_rejected_order(cur, bronze_row, reason)
            rejected += 1
            continue
        insert_clean_order(cur, bronze_row, clean)
        accepted += 1

    cur.execute(
        """
        UPDATE etl.batch_run
        SET silver_completed_at = NOW(),
            silver_accepted_count = %s,
            silver_rejected_count = %s
        WHERE batch_id = %s;
        """,
        (accepted, rejected, batch_id),
    )
    return accepted, rejected


def require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


# def upsert_customer(cur, customer):
def upsert_customer(cur, row: dict[str, Any]) -> int:
    cur.execute(
        """
        INSERT INTO dw.dim_customer (customer_id, customer_name, phone_number, email, membership)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (customer_id) DO UPDATE
        SET customer_name = EXCLUDED.customer_name,
            phone_number = EXCLUDED.phone_number,
            email = EXCLUDED.email,
            membership = EXCLUDED.membership
        RETURNING customer_key;
        """,
        (
            row["customer_id"],
            row["customer_name"],
            row.get("customer_phone_number"),
            row.get("customer_email"),
            row.get("customer_membership"),
        ),
    )
    return cur.fetchone()[0]


def upsert_product(cur, row: dict[str, Any]) -> int:
    cur.execute(
        """
        INSERT INTO dw.dim_product (
            product_id,
            product_name,
            product_category,
            product_brand,
            quantity_in_stock
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (product_id) DO UPDATE
        SET product_name = EXCLUDED.product_name,
            product_category = EXCLUDED.product_category,
            product_brand = EXCLUDED.product_brand,
            quantity_in_stock = EXCLUDED.quantity_in_stock
        RETURNING product_key;
        """,
        (
            row["product_id"],
            row["product_name"],
            row.get("product_category"),
            row.get("product_brand"),
            row.get("quantity_in_stock"),
        ),
    )
    return cur.fetchone()[0]


def upsert_retailer(cur, row: dict[str, Any]) -> int:
    cur.execute(
        """
        INSERT INTO dw.dim_retailer (
            retailer_id,
            retailer_name,
            phone_number,
            email,
            rating
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (retailer_id) DO UPDATE
        SET retailer_name = EXCLUDED.retailer_name,
            phone_number = EXCLUDED.phone_number,
            email = EXCLUDED.email,
            rating = EXCLUDED.rating
        RETURNING retailer_key;
        """,
        (
            row["retailer_id"],
            row["retailer_name"],
            row.get("retailer_phone_number"),
            row.get("retailer_email"),
            row.get("retailer_rating"),
        ),
    )
    return cur.fetchone()[0]


def upsert_address(cur, row: dict[str, Any]) -> int:
    cur.execute(
        """
        INSERT INTO dw.dim_address (street, commune_ward, province_city)
        VALUES (%s, %s, %s)
        ON CONFLICT (street, commune_ward, province_city) DO UPDATE
        SET street = EXCLUDED.street
        RETURNING address_key;
        """,
        (
            row["street"],
            row["commune_ward"],
            row["province_city"],
        ),
    )
    return cur.fetchone()[0]


def upsert_payment(cur, row: dict[str, Any]) -> int:
    cur.execute(
        """
        INSERT INTO dw.dim_payment (payment_type, method_provider)
        VALUES (%s, %s)
        ON CONFLICT (payment_type, method_provider) DO UPDATE
        SET payment_type = EXCLUDED.payment_type
        RETURNING payment_key;
        """,
        (
            row["payment_type"],
            row["method_provider"],
        ),
    )
    return cur.fetchone()[0]


def upsert_date(cur, sold_at: datetime) -> int:
    full_date = sold_at.date()
    date_key = int(full_date.strftime("%Y%m%d"))
    cur.execute(
        """
        INSERT INTO dw.dim_date (date_key, full_date, day, month, year)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (date_key) DO UPDATE
        SET full_date = EXCLUDED.full_date,
            day = EXCLUDED.day,
            month = EXCLUDED.month,
            year = EXCLUDED.year
        RETURNING date_key;
        """,
        (
            date_key,
            full_date,
            full_date.day,
            full_date.month,
            full_date.year,
        ),
    )
    return cur.fetchone()[0]


def upsert_fact_sale(cur, row: dict[str, Any], batch_id: uuid.UUID) -> None:
    customer_key = upsert_customer(cur, row)
    product_key = upsert_product(cur, row)
    retailer_key = upsert_retailer(cur, row)
    address_key = upsert_address(cur, row)
    payment_key = upsert_payment(cur, row)
    date_key = upsert_date(cur, row["sold_at"])

    cur.execute(
        """
        INSERT INTO dw.fact_sales (
            order_id,
            customer_key,
            retailer_key,
            product_key,
            quantity,
            price,
            discount,
            tax,
            date_key,
            address_key,
            payment_key,
            batch_id,
            silver_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (order_id) DO UPDATE
        SET customer_key = EXCLUDED.customer_key,
            retailer_key = EXCLUDED.retailer_key,
            product_key = EXCLUDED.product_key,
            quantity = EXCLUDED.quantity,
            price = EXCLUDED.price,
            discount = EXCLUDED.discount,
            tax = EXCLUDED.tax,
            date_key = EXCLUDED.date_key,
            address_key = EXCLUDED.address_key,
            payment_key = EXCLUDED.payment_key,
            batch_id = EXCLUDED.batch_id,
            silver_id = EXCLUDED.silver_id,
            loaded_at = NOW();
        """,
        (
            row["order_id"],
            customer_key,
            retailer_key,
            product_key,
            row["quantity"],
            row["price"],
            row["discount"],
            row["tax"],
            date_key,
            address_key,
            payment_key,
            batch_id,
            row["silver_id"],
        ),
    )


def load_gold(cur, batch_id: uuid.UUID) -> int:
    cur.execute(
        """
        SELECT
            silver_id,
            order_id,
            sold_at,
            quantity,
            price,
            discount,
            tax,
            customer_id,
            customer_name,
            customer_phone_number,
            customer_email,
            customer_membership,
            product_id,
            product_name,
            product_category,
            product_brand,
            quantity_in_stock,
            retailer_id,
            retailer_name,
            retailer_phone_number,
            retailer_email,
            retailer_rating,
            street,
            commune_ward,
            province_city,
            payment_type,
            method_provider
        FROM silver.orders_clean
        WHERE batch_id = %s
        ORDER BY silver_id;
        """,
        (batch_id,),
    )
    rows = cur.fetchall()
    colnames = [desc.name for desc in cur.description]

    loaded = 0
    for row in rows:
        upsert_fact_sale(cur, dict(zip(colnames, row)), batch_id)
        loaded += 1

    cur.execute(
        """
        UPDATE etl.batch_run
        SET gold_completed_at = NOW(),
            gold_loaded_count = %s
        WHERE batch_id = %s;
        """,
        (loaded, batch_id),
    )
    return loaded


def mongo_uri_from_env() -> str:
    configured_uri = os.getenv("MONGO_URI")
    if configured_uri:
        return configured_uri

    mongo_user = require_env("MONGO_INITDB_ROOT_USERNAME")
    mongo_password = require_env("MONGO_INITDB_ROOT_PASSWORD")
    mongo_host = os.getenv("MONGO_HOST", "mongodb")
    mongo_port = os.getenv("MONGO_PORT", "27017")
    return (
        f"mongodb://{mongo_user}:{mongo_password}"
        f"@{mongo_host}:{mongo_port}/?authSource=admin"
    )


def finish_batch(cur, batch_id: uuid.UUID, dq_passed: bool) -> None:
    status = "success" if dq_passed else "failed"
    error_message = None if dq_passed else "Data quality checks failed"
    cur.execute(
        """
        UPDATE etl.batch_run
        SET finished_at = NOW(),
            status = %s,
            error_message = %s
        WHERE batch_id = %s;
        """,
        (status, error_message, batch_id),
    )


def run_pipeline() -> uuid.UUID:
    mongo_uri = mongo_uri_from_env()
    mongo_db_name = os.getenv("MONGO_DB", "landing")
    collection_name = os.getenv("MONGO_COLLECTION", "orders_raw")

    mongo_client = MongoClient(mongo_uri)
    pg_conn = pg_connect()
    batch_id = uuid.uuid4()
    extracted = 0
    accepted = 0
    rejected = 0
    loaded = 0
    dq_passed = False

    try:
        collection = mongo_client[mongo_db_name][collection_name]
        with pg_conn.cursor() as cur:
            start_batch(cur, batch_id, mongo_db_name, collection_name)
        pg_conn.commit()

        with pg_conn.cursor() as cur:
            extracted = extract_bronze(cur, batch_id, collection, collection_name)
        pg_conn.commit()

        with pg_conn.cursor() as cur:
            accepted, rejected = load_silver(cur, batch_id)
        pg_conn.commit()

        with pg_conn.cursor() as cur:
            loaded = load_gold(cur, batch_id)
        pg_conn.commit()

        with pg_conn.cursor() as cur:
            dq_passed = run_data_quality_checks(cur, batch_id)
            finish_batch(cur, batch_id, dq_passed)
        pg_conn.commit()

        if not dq_passed:
            raise RuntimeError(f"Data quality checks failed for batch {batch_id}")

    except Exception as exc:
        try:
            update_batch_failure(pg_conn, batch_id, exc)
        except Exception:
            pg_conn.rollback()
        raise
    finally:
        mongo_client.close()
        pg_conn.close()

    print(
        "Batch "
        f"{batch_id} complete: extracted={extracted}, "
        f"silver_accepted={accepted}, silver_rejected={rejected}, "
        f"gold_loaded={loaded}, dq_passed={dq_passed}"
    )
    return batch_id


def main() -> None:
    run_pipeline()


if __name__ == "__main__":
    main()
