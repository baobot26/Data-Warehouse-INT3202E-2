import os

from bson.objectid import ObjectId
from pymongo import MongoClient

from .utils import require_env


def get_mongo_connection():
    host = require_env("MONGO_HOST")
    port = int(require_env("MONGO_PORT"))
    user = require_env("MONGO_INITDB_ROOT_USERNAME")
    password = require_env("MONGO_INITDB_ROOT_PASSWORD")
    db_name = require_env("MONGO_DB")

    mongo_uri = f"mongodb://{user}:{password}@{host}:{port}/?authSource=admin"
    client = MongoClient(mongo_uri)

    return client[db_name]


def extract_orders(last_watermark=None):
    db = get_mongo_connection()
    collection_name = os.getenv("MONGO_COLLECTION", "orders_raw")
    collection = db[collection_name]

    query = {}
    if last_watermark:
        fallback_id = ObjectId.from_datetime(last_watermark)
        query = {
            "$or": [
                {"updated_at": {"$gt": last_watermark}},
                {"updated_at": {"$exists": False}, "_id": {"$gt": fallback_id}},
            ]
        }

    cursor = collection.find(query).batch_size(1000)
    for doc in cursor:
        yield doc
