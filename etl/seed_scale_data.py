"""Generate deterministic MongoDB order documents for scale testing."""

from __future__ import annotations

import argparse
import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from etl.utils import require_env


FIRST_NAMES = [
    "An",
    "Bao",
    "Chi",
    "Dung",
    "Giang",
    "Ha",
    "Khanh",
    "Linh",
    "Minh",
    "Nam",
    "Phuong",
    "Quang",
    "Thao",
    "Trang",
    "Vy",
]
LAST_NAMES = [
    "Nguyen",
    "Tran",
    "Le",
    "Pham",
    "Hoang",
    "Phan",
    "Vu",
    "Dang",
    "Bui",
    "Do",
]
MEMBERSHIPS = ["Bronze", "Silver", "Gold", "Platinum"]
PRODUCTS = [
    ("PRO-AUD", "Wireless Earbuds", "Audio", "SonicWave", 120.00),
    ("PRO-COM", "Gaming Laptop", "Computers", "NovaTech", 899.00),
    ("PRO-ACC", "USB-C Charger", "Accessories", "Voltix", 35.50),
    ("PRO-MOB", "Smartphone", "Mobile", "Aster", 699.00),
    ("PRO-HOM", "Robot Vacuum", "Home", "Cleanly", 249.00),
    ("PRO-CAM", "Action Camera", "Cameras", "PixPro", 180.00),
    ("PRO-GAM", "Mechanical Keyboard", "Gaming", "KeyForge", 88.00),
    ("PRO-TAB", "Tablet", "Mobile", "Aster", 329.00),
]
RETAILERS = [
    ("RET-001", "Downtown Store", "02873000001", "downtown@example.com", 4.7),
    ("RET-002", "Tech Mall", "02873000002", "techmall@example.com", 4.9),
    ("RET-003", "Online Outlet", "02873000003", "online@example.com", 4.5),
    ("RET-004", "Campus Kiosk", "02873000004", "campus@example.com", 4.2),
]
ADDRESSES = [
    ("12 Le Loi", "Ben Nghe", "Ho Chi Minh City"),
    ("89 Tran Hung Dao", "Cau Ong Lanh", "Ho Chi Minh City"),
    ("45 Nguyen Trai", "Ben Thanh", "Ho Chi Minh City"),
    ("18 Bach Dang", "Hai Chau", "Da Nang"),
    ("77 Cau Giay", "Dich Vong", "Ha Noi"),
]
PAYMENTS = [
    ("Card", "Visa"),
    ("Card", "Mastercard"),
    ("E-Wallet", "MoMo"),
    ("E-Wallet", "ZaloPay"),
    ("Bank Transfer", "Vietcombank"),
    ("Cash", "COD"),
]
START_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)


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


def build_order(index: int, prefix: str) -> dict[str, Any]:
    customer_number = (index % 5000) + 1
    product_number = (index % 1000) + 1
    product_group = PRODUCTS[index % len(PRODUCTS)]
    retailer = RETAILERS[(index // 7) % len(RETAILERS)]
    address = ADDRESSES[(index // 11) % len(ADDRESSES)]
    payment = PAYMENTS[(index // 5) % len(PAYMENTS)]

    quantity = (index % 5) + 1
    base_price = product_group[4]
    price_multiplier = 0.90 + ((index % 21) / 100)
    price = round(base_price * price_multiplier, 2)
    gross_amount = price * quantity
    discount = round(gross_amount * ((index % 4) * 0.03), 2)
    tax = round((gross_amount - discount) * 0.08, 2)
    sold_at = START_DATE + timedelta(days=index % 730, minutes=(index * 17) % 1440)

    first_name = FIRST_NAMES[index % len(FIRST_NAMES)]
    last_name = LAST_NAMES[(index // len(FIRST_NAMES)) % len(LAST_NAMES)]
    customer_id = f"CUS-{customer_number:05d}"
    product_id = f"{product_group[0]}-{product_number:05d}"

    return {
        "order_id": f"{prefix}{index:08d}",
        "sold_at": sold_at,
        "quantity": quantity,
        "price": price,
        "discount": discount,
        "tax": tax,
        "customer": {
            "customer_id": customer_id,
            "customer_name": f"{last_name} {first_name} {customer_number:05d}",
            "phone_number": f"09{customer_number:08d}",
            "email": f"{customer_id.lower()}@example.com",
            "membership": MEMBERSHIPS[index % len(MEMBERSHIPS)],
        },
        "product": {
            "product_id": product_id,
            "product_name": f"{product_group[1]} {product_number:05d}",
            "product_category": product_group[2],
            "product_brand": product_group[3],
            "quantity_in_stock": 20 + (index % 500),
        },
        "retailer": {
            "retailer_id": retailer[0],
            "retailer_name": retailer[1],
            "phone_number": retailer[2],
            "email": retailer[3],
            "rating": retailer[4],
        },
        "address": {
            "street": address[0],
            "commune_ward": address[1],
            "province_city": address[2],
        },
        "payment": {
            "payment_type": payment[0],
            "method_provider": payment[1],
        },
    }


def iter_orders(start_index: int, count: int, prefix: str) -> Iterator[dict[str, Any]]:
    for offset in range(count):
        yield build_order(start_index + offset, prefix)


def seed_orders(
    collection: Any,
    *,
    count: int,
    start_index: int,
    batch_size: int,
    prefix: str,
    reset: bool,
) -> int:
    from pymongo import ReplaceOne

    collection.create_index("order_id", unique=True)

    if reset:
        collection.delete_many({"order_id": {"$regex": f"^{re.escape(prefix)}"}})

    written = 0
    total_batches = math.ceil(count / batch_size)
    batch: list[Any] = []
    batch_number = 1

    for order in iter_orders(start_index, count, prefix):
        batch.append(ReplaceOne({"order_id": order["order_id"]}, order, upsert=True))
        if len(batch) == batch_size:
            collection.bulk_write(batch, ordered=False)
            written += len(batch)
            print(f"seeded {written}/{count} orders ({batch_number}/{total_batches} batches)")
            batch.clear()
            batch_number += 1

    if batch:
        collection.bulk_write(batch, ordered=False)
        written += len(batch)
        print(f"seeded {written}/{count} orders ({batch_number}/{total_batches} batches)")

    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed deterministic synthetic order documents into MongoDB."
    )
    parser.add_argument(
        "--count",
        type=positive_int,
        default=int(os.getenv("SCALE_ORDER_COUNT", "10000")),
        help="number of synthetic orders to upsert",
    )
    parser.add_argument(
        "--start-index",
        type=non_negative_int,
        default=int(os.getenv("SCALE_START_INDEX", "1")),
        help="first numeric index used in generated order_id values",
    )
    parser.add_argument(
        "--batch-size",
        type=positive_int,
        default=int(os.getenv("SCALE_BATCH_SIZE", "1000")),
        help="MongoDB bulk-write size",
    )
    parser.add_argument(
        "--prefix",
        default=os.getenv("SCALE_ORDER_PREFIX", "ORD-SCALE-"),
        help="order_id prefix for generated records",
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
        "--reset",
        action="store_true",
        help="delete existing generated records with the same prefix before seeding",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    from pymongo import MongoClient

    client = MongoClient(mongo_uri_from_env())
    try:
        collection = client[args.mongo_db][args.collection]
        written = seed_orders(
            collection,
            count=args.count,
            start_index=args.start_index,
            batch_size=args.batch_size,
            prefix=args.prefix,
            reset=args.reset,
        )
    finally:
        client.close()

    print(
        f"Done. Upserted {written} generated orders into "
        f"{args.mongo_db}.{args.collection}."
    )


if __name__ == "__main__":
    main()
