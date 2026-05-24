from .utils import to_decimal, normalize_timestamp

def _normalize_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None

def _get_current_customer_key(cur, customer_id):
    cur.execute(
        """
        SELECT customer_key
        FROM dw.dim_customer
        WHERE customer_id = %s
          AND is_current = TRUE
        ORDER BY valid_from DESC, customer_key DESC
        LIMIT 1;
        """,
        (customer_id,),
    )
    row = cur.fetchone()
    return row[0] if row else None

def upsert_customer(cur, customer):
    customer_id = _normalize_text(customer.get("customer_id"))
    customer_name = _normalize_text(customer.get("customer_name"))
    phone_number = _normalize_text(customer.get("phone_number"))
    email = _normalize_text(customer.get("email"))
    membership = _normalize_text(customer.get("membership"))

    if customer_id is None:
        raise ValueError("customer_id is required")
    if customer_name is None:
        raise ValueError("customer_name is required")

    cur.execute(
        """
        WITH closed AS (
            UPDATE dw.dim_customer
            SET valid_to = NOW(),
                is_current = FALSE
            WHERE customer_id = %s
              AND is_current = TRUE
              AND (
                customer_name IS DISTINCT FROM %s
                OR phone_number IS DISTINCT FROM %s
                OR email IS DISTINCT FROM %s
                OR membership IS DISTINCT FROM %s
              )
            RETURNING valid_to
        )
        INSERT INTO dw.dim_customer (
            customer_id,
            customer_name,
            phone_number,
            email,
            membership,
            valid_from,
            valid_to,
            is_current
        )
        SELECT
            %s,
            %s,
            %s,
            %s,
            %s,
            closed.valid_to,
            NULL,
            TRUE
        FROM closed
        RETURNING customer_key;
        """,
        (
            customer_id,
            customer_name,
            phone_number,
            email,
            membership,
            customer_id,
            customer_name,
            phone_number,
            email,
            membership,
        ),
    )
    inserted_changed_row = cur.fetchone()
    if inserted_changed_row:
        return inserted_changed_row[0]

    current_customer_key = _get_current_customer_key(cur, customer_id)
    if current_customer_key is not None:
        return current_customer_key

    cur.execute(
        """
        INSERT INTO dw.dim_customer (
            customer_id,
            customer_name,
            phone_number,
            email,
            membership,
            valid_from,
            valid_to,
            is_current
        )
        VALUES (%s, %s, %s, %s, %s, NOW(), NULL, TRUE)
        ON CONFLICT DO NOTHING
        RETURNING customer_key;
        """,
        (
            customer_id,
            customer_name,
            phone_number,
            email,
            membership,
        ),
    )
    inserted_new_row = cur.fetchone()
    if inserted_new_row:
        return inserted_new_row[0]

    current_customer_key = _get_current_customer_key(cur, customer_id)
    if current_customer_key is None:
        raise RuntimeError(f"Unable to resolve current customer_key for customer_id={customer_id}")
    return current_customer_key

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
