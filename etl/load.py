from .utils import to_decimal, normalize_timestamp

def upsert_customer(cur, customer):
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
            customer["customer_id"],
            customer["customer_name"],
            customer.get("phone_number"),
            customer.get("email"),
            customer.get("membership"),
        ),
    )
    return cur.fetchone()[0]

def upsert_product(cur, product):
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
            product["product_id"],
            product["product_name"],
            product.get("product_category"),
            product.get("product_brand"),
            product.get("quantity_in_stock"),
        ),
    )
    return cur.fetchone()[0]

def upsert_retailer(cur, retailer):
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
            retailer["retailer_id"],
            retailer["retailer_name"],
            retailer.get("phone_number"),
            retailer.get("email"),
            retailer.get("rating"),
        ),
    )
    return cur.fetchone()[0]

def upsert_address(cur, address):
    cur.execute(
        """
        INSERT INTO dw.dim_address (street, commune_ward, province_city)
        VALUES (%s, %s, %s)
        ON CONFLICT (street, commune_ward, province_city) DO UPDATE
        SET street = EXCLUDED.street
        RETURNING address_key;
        """,
        (
            address["street"],
            address["commune_ward"],
            address["province_city"],
        ),
    )
    return cur.fetchone()[0]

def upsert_payment(cur, payment):
    cur.execute(
        """
        INSERT INTO dw.dim_payment (payment_type, method_provider)
        VALUES (%s, %s)
        ON CONFLICT (payment_type, method_provider) DO UPDATE
        SET payment_type = EXCLUDED.payment_type
        RETURNING payment_key;
        """,
        (
            payment["payment_type"],
            payment["method_provider"],
        ),
    )
    return cur.fetchone()[0]

def upsert_date(cur, sold_at):
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

def upsert_fact_sale(cur, order):
    sold_at = normalize_timestamp(order["sold_at"])
    customer_key = upsert_customer(cur, order["customer"])
    product_key = upsert_product(cur, order["product"])
    retailer_key = upsert_retailer(cur, order["retailer"])
    address_key = upsert_address(cur, order["address"])
    payment_key = upsert_payment(cur, order["payment"])
    date_key = upsert_date(cur, sold_at)

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
            payment_key
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            loaded_at = NOW();
        """,
        (
            order["order_id"],
            customer_key,
            retailer_key,
            product_key,
            order["quantity"],
            to_decimal(order["price"]),
            to_decimal(order.get("discount", 0)),
            to_decimal(order.get("tax", 0)),
            date_key,
            address_key,
            payment_key,
        ),
    )
