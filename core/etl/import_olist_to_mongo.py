"""Import Olist public e-commerce CSVs into the MongoDB raw orders collection."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Iterable

from .utils import require_env


REQUIRED_CSV_FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
}
OPTIONAL_CSV_FILES = {
    "category_translation": "product_category_name_translation.csv",
}


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be greater than or equal to 0")
    return parsed


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


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    text = str(value).strip()
    return not text or text.lower() in {"nan", "none", "null", "nat"}


def text_value(value: Any, fallback: str) -> str:
    return fallback if is_blank(value) else str(value).strip()


def short_id(value: Any, fallback: str = "unknown") -> str:
    text = text_value(value, fallback)
    return text[:8]


def numeric_value(value: Any, field_name: str, *, default: float | None = None) -> float:
    if is_blank(value):
        if default is not None:
            return default
        raise ValueError(f"missing {field_name}")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field_name}: {value!r}") from exc
    if parsed < 0:
        raise ValueError(f"{field_name} must be greater than or equal to 0")
    return round(parsed, 2)


def integer_value(value: Any, *, default: int | None = None) -> int | None:
    if is_blank(value):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def category_name(row: Any) -> str:
    category = text_value(
        row.get("product_category_name_english"),
        text_value(row.get("product_category_name"), "unknown"),
    )
    return category.replace("_", " ").strip().title()


def parse_sold_at(value: Any) -> Any:
    import pandas as pd

    if is_blank(value):
        raise ValueError("missing order_purchase_timestamp")
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"invalid order_purchase_timestamp: {value!r}")
    return parsed.to_pydatetime()


def read_csv_files(source_dir: Path) -> dict[str, Any]:
    import pandas as pd

    missing = [
        filename
        for filename in REQUIRED_CSV_FILES.values()
        if not (source_dir / filename).is_file()
    ]
    if missing:
        files = ", ".join(missing)
        raise FileNotFoundError(f"Missing required Olist CSV file(s): {files}")

    frames = {
        key: pd.read_csv(source_dir / filename, dtype=str, keep_default_na=False)
        for key, filename in REQUIRED_CSV_FILES.items()
    }

    for key, filename in OPTIONAL_CSV_FILES.items():
        path = source_dir / filename
        if path.is_file():
            frames[key] = pd.read_csv(path, dtype=str, keep_default_na=False)

    return frames


def first_payment_per_order(payments: Any) -> Any:
    payments = payments.copy()
    if "payment_sequential" in payments.columns:
        payments["_payment_sequence_sort"] = payments["payment_sequential"].apply(
            lambda value: integer_value(value, default=999999)
        )
    else:
        payments["_payment_sequence_sort"] = 999999
    return (
        payments.sort_values(["order_id", "_payment_sequence_sort"])
        .drop_duplicates("order_id", keep="first")
        .drop(columns=["_payment_sequence_sort"])
    )


def joined_olist_rows(source_dir: Path, order_status: str) -> Any:
    frames = read_csv_files(source_dir)

    products = frames["products"]
    if "category_translation" in frames:
        products = products.merge(
            frames["category_translation"],
            on="product_category_name",
            how="left",
        )

    rows = (
        frames["order_items"]
        .merge(frames["orders"], on="order_id", how="inner")
        .merge(frames["customers"], on="customer_id", how="left")
        .merge(products, on="product_id", how="left")
        .merge(frames["sellers"], on="seller_id", how="left")
        .merge(first_payment_per_order(frames["payments"]), on="order_id", how="left")
    )

    if order_status.lower() != "all":
        rows = rows[
            rows["order_status"].astype(str).str.lower() == order_status.lower()
        ]

    rows["_order_item_sort"] = rows["order_item_id"].apply(
        lambda value: integer_value(value, default=0)
    )
    return rows.sort_values(
        ["order_purchase_timestamp", "order_id", "_order_item_sort"],
        kind="stable",
    )


def build_order_document(row: Any, *, prefix: str) -> dict[str, Any]:
    source_order_id = text_value(row.get("order_id"), "")
    source_order_item_id = text_value(row.get("order_item_id"), "1")
    if not source_order_id:
        raise ValueError("missing order_id")

    category = category_name(row)
    product_id = text_value(row.get("product_id"), "unknown-product")
    customer_id = text_value(
        row.get("customer_unique_id"),
        text_value(row.get("customer_id"), "unknown-customer"),
    )
    seller_id = text_value(row.get("seller_id"), "unknown-seller")
    payment_type = text_value(row.get("payment_type"), "unknown")

    return {
        "order_id": f"{prefix}{source_order_id}-{source_order_item_id}",
        "sold_at": parse_sold_at(row.get("order_purchase_timestamp")),
        "quantity": 1,
        "price": numeric_value(row.get("price"), "price"),
        "discount": 0,
        "tax": 0,
        "customer": {
            "customer_id": customer_id,
            "customer_name": f"Olist Customer {short_id(customer_id)}",
            "phone_number": None,
            "email": None,
            "membership": "Standard",
        },
        "product": {
            "product_id": product_id,
            "product_name": f"{category} Product {short_id(product_id)}",
            "product_category": category,
            "product_brand": "Olist",
            "quantity_in_stock": None,
        },
        "retailer": {
            "retailer_id": seller_id,
            "retailer_name": f"Olist Seller {short_id(seller_id)}",
            "phone_number": None,
            "email": None,
            "rating": None,
        },
        "address": {
            "street": f"ZIP {text_value(row.get('customer_zip_code_prefix'), 'unknown')}",
            "commune_ward": text_value(row.get("customer_city"), "unknown-city"),
            "province_city": text_value(row.get("customer_state"), "unknown-state"),
        },
        "payment": {
            "payment_type": payment_type,
            "method_provider": "Olist",
        },
        "source": {
            "dataset": "olist",
            "source_order_id": source_order_id,
            "source_order_item_id": integer_value(source_order_item_id, default=1),
            "source_customer_id": text_value(row.get("customer_id"), "unknown-customer"),
            "source_customer_unique_id": customer_id,
            "source_product_id": product_id,
            "source_seller_id": seller_id,
            "source_order_status": text_value(row.get("order_status"), "unknown"),
            "payment_installments": integer_value(
                row.get("payment_installments"),
                default=None,
            ),
            "payment_value": numeric_value(
                row.get("payment_value"),
                "payment_value",
                default=0,
            ),
            "freight_value": numeric_value(
                row.get("freight_value"),
                "freight_value",
                default=0,
            ),
        },
    }


def validate_document(document: dict[str, Any]) -> None:
    required_top_level = ("order_id", "sold_at", "quantity", "price", "discount", "tax")
    missing_top_level = [
        field
        for field in required_top_level
        if field not in document or is_blank(document[field])
    ]
    if missing_top_level:
        raise ValueError(f"missing required field(s): {', '.join(missing_top_level)}")

    if int(document["quantity"]) <= 0:
        raise ValueError("quantity must be greater than 0")
    for amount_field in ("price", "discount", "tax"):
        if numeric_value(document[amount_field], amount_field) < 0:
            raise ValueError(f"{amount_field} must be greater than or equal to 0")

    for nested_key in ("customer", "product", "retailer", "address", "payment"):
        if not isinstance(document.get(nested_key), dict):
            raise ValueError(f"missing or invalid {nested_key}")

    required_nested = {
        "customer.customer_id": document["customer"].get("customer_id"),
        "customer.customer_name": document["customer"].get("customer_name"),
        "product.product_id": document["product"].get("product_id"),
        "product.product_name": document["product"].get("product_name"),
        "retailer.retailer_id": document["retailer"].get("retailer_id"),
        "retailer.retailer_name": document["retailer"].get("retailer_name"),
        "address.street": document["address"].get("street"),
        "address.commune_ward": document["address"].get("commune_ward"),
        "address.province_city": document["address"].get("province_city"),
        "payment.payment_type": document["payment"].get("payment_type"),
        "payment.method_provider": document["payment"].get("method_provider"),
    }
    missing_nested = [
        field for field, value in required_nested.items() if is_blank(value)
    ]
    if missing_nested:
        raise ValueError(f"missing required field(s): {', '.join(missing_nested)}")


def load_olist_documents(
    source_dir: Path,
    *,
    prefix: str,
    order_status: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows = joined_olist_rows(source_dir, order_status)
    if limit:
        rows = rows.head(limit)

    documents: list[dict[str, Any]] = []
    errors: list[str] = []

    for row_number, row in enumerate(rows.to_dict("records"), start=1):
        try:
            document = build_order_document(row, prefix=prefix)
            validate_document(document)
            documents.append(document)
        except Exception as exc:
            source_order_id = row.get("order_id", "<unknown>")
            errors.append(f"row {row_number} order {source_order_id}: {exc}")
            if len(errors) >= 10:
                break

    if errors:
        joined_errors = "\n- ".join(errors)
        raise ValueError(f"Invalid Olist rows:\n- {joined_errors}")
    if not documents:
        raise RuntimeError("No Olist order documents were built from the input files.")

    return documents


def upsert_documents(
    collection: Any,
    documents: Iterable[dict[str, Any]],
    *,
    batch_size: int,
    prefix: str,
    reset_prefix: bool,
) -> int:
    from pymongo import ReplaceOne

    collection.create_index("order_id", unique=True)

    if reset_prefix:
        collection.delete_many({"order_id": {"$regex": f"^{re.escape(prefix)}"}})

    written = 0
    batch: list[Any] = []

    for document in documents:
        batch.append(
            ReplaceOne({"order_id": document["order_id"]}, document, upsert=True)
        )
        if len(batch) == batch_size:
            collection.bulk_write(batch, ordered=False)
            written += len(batch)
            print(f"imported {written} Olist order item documents")
            batch.clear()

    if batch:
        collection.bulk_write(batch, ordered=False)
        written += len(batch)
        print(f"imported {written} Olist order item documents")

    return written


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert Olist public e-commerce CSVs into raw MongoDB order "
            "documents compatible with the existing Bronze/Silver/Gold ETL."
        )
    )
    parser.add_argument(
        "--source-dir",
        default=os.getenv("OLIST_SOURCE_DIR", "data/olist/raw"),
        help="directory containing the Olist CSV files",
    )
    parser.add_argument(
        "--mongo-db",
        default=os.getenv("MONGO_DB", "landing"),
        help="MongoDB database name",
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("MONGO_COLLECTION", "orders_raw"),
        help="MongoDB collection name",
    )
    parser.add_argument(
        "--prefix",
        default=os.getenv("OLIST_ORDER_PREFIX", "OLIST-"),
        help="order_id prefix for imported Olist records",
    )
    parser.add_argument(
        "--batch-size",
        type=positive_int,
        default=int(os.getenv("OLIST_BATCH_SIZE", "1000")),
        help="MongoDB bulk-write size",
    )
    parser.add_argument(
        "--limit",
        type=non_negative_int,
        default=int(os.getenv("OLIST_LIMIT", "0")),
        help="maximum number of Olist order item documents to import; 0 imports all",
    )
    parser.add_argument(
        "--order-status",
        default=os.getenv("OLIST_ORDER_STATUS", "delivered"),
        help="Olist order status to import, or 'all'",
    )
    parser.add_argument(
        "--reset-prefix",
        action="store_true",
        help="delete existing MongoDB records with the same prefix before import",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="read, join, convert, and validate without writing to MongoDB",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    source_dir = Path(args.source_dir)

    documents = load_olist_documents(
        source_dir,
        prefix=args.prefix,
        order_status=args.order_status,
        limit=args.limit,
    )

    if args.dry_run:
        print(f"Validated {len(documents)} Olist order item documents.")
        print(json.dumps(documents[0], default=str, indent=2, sort_keys=True))
        return

    from pymongo import MongoClient

    client = MongoClient(mongo_uri_from_env())
    try:
        collection = client[args.mongo_db][args.collection]
        written = upsert_documents(
            collection,
            documents,
            batch_size=args.batch_size,
            prefix=args.prefix,
            reset_prefix=args.reset_prefix,
        )
    finally:
        client.close()

    print(
        f"Done. Upserted {written} Olist order item documents into "
        f"{args.mongo_db}.{args.collection}."
    )


if __name__ == "__main__":
    main()
