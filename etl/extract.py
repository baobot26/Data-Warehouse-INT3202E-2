from bson.objectid import ObjectId
from pymongo import MongoClient
from etl.utils import require_env

def get_mongo_connection():
    """Tạo kết nối tới MongoDB sử dụng thông tin từ file .env"""
    host = require_env("MONGO_HOST")
    port = int(require_env("MONGO_PORT"))
    user = require_env("MONGO_INITDB_ROOT_USERNAME")
    password = require_env("MONGO_INITDB_ROOT_PASSWORD")
    db_name = require_env("MONGO_DB")
    
    # Khai báo chính xác biến mongo_uri để truyền vào MongoClient
    mongo_uri = f"mongodb://{user}:{password}@{host}:{port}/?authSource=admin"
    client = MongoClient(mongo_uri)
    
    return client[db_name]

def extract_orders(last_watermark=None):
    """
    Extract dữ liệu từ MongoDB.
    Sử dụng yield để tối ưu RAM (trả về Generator thay vì List).
    """
    db = get_mongo_connection()
    collection = db["orders"]  # Đảm bảo đây đúng là tên collection
    
    query = {}
    if last_watermark:
        fallback_id = ObjectId.from_datetime(last_watermark)
        query = {
            "$or": [
                {"updated_at": {"$gt": last_watermark}},
                {"updated_at": {"$exists": False}, "_id": {"$gt": fallback_id}}
            ]
        }
    
    # Sử dụng find() và yield từng dòng
    cursor = collection.find(query).batch_size(1000)
    for doc in cursor:
        yield doc