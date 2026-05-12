import logging
from .utils import to_decimal, normalize_timestamp

logger = logging.getLogger(__name__)

def transform_order(order):
    """
    Quy tắc chuyển đổi dữ liệu (Business Logic)
    """
    try:
        # 1. Chuẩn hóa thời gian (về định dạng Datetime của Python)
        order["sold_at"] = normalize_timestamp(order["sold_at"])

        # 2. Ép kiểu và xử lý giá trị mặc định cho số tiền
        # Nếu thiếu discount/tax thì mặc định là 0
        order["price"] = to_decimal(order.get("price", 0))
        order["discount"] = to_decimal(order.get("discount", 0))
        order["tax"] = to_decimal(order.get("tax", 0))

        # 3. Đảm bảo số lượng phải là số nguyên dương
        qty = int(order.get("quantity", 0))
        order["quantity"] = qty if qty > 0 else 1 

        # 4. Làm sạch dữ liệu văn bản (Xóa khoảng trắng thừa)
        if "customer" in order:
            order["customer"]["customer_name"] = order["customer"]["customer_name"].strip().title()
        
        return order

    except Exception as e:
        logger.error(f"Lỗi Transform bản ghi {order.get('order_id')}: {e}")
        raise e # Ném lỗi ra ngoài để main_etl ghi vào bảng error_records