import os
from pymongo import MongoClient
from .utils import require_env   # dùng import tương đối trong package etl

def extract_orders():
    mongo_user = require_env("MONGO_INITDB_ROOT_USERNAME")
    mongo_password = require_env("MONGO_INITDB_ROOT_PASSWORD")
    mongo_host = os.getenv("MONGO_HOST", "mongodb")
    mongo_port = os.getenv("MONGO_PORT", "27017")
    mongo_db_name = os.getenv("MONGO_DB", "landing")

    mongo_uri = (
        f"mongodb://{mongo_user}:{mongo_password}"
        f"@{mongo_host}:{mongo_port}/?authSource=admin"
    )

    client = MongoClient(mongo_uri)
    orders = list(client[mongo_db_name]["orders_raw"].find())
    client.close()
    return orders
