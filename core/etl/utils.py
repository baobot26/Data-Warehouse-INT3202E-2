import os
from datetime import datetime
from decimal import Decimal

def to_decimal(value):
    return Decimal(str(value))

def normalize_timestamp(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError(f"Unsupported sold_at value: {value!r}")

def require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
