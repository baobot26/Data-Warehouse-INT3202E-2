import json
from decimal import Decimal
from typing import Any


def _count(cur, sql: str, params: tuple[Any, ...]) -> int:
    cur.execute(sql, params)
    return int(cur.fetchone()[0])


def _decimal(cur, sql: str, params: tuple[Any, ...]) -> Decimal:
    cur.execute(sql, params)
    return Decimal(cur.fetchone()[0])


def record_check_result(
    cur,
    batch_id,
    layer: str,
    check_name: str,
    severity: str,
    checked_count: int,
    failed_count: int,
    details: dict[str, Any] | None = None,
) -> bool:
    status = "passed" if failed_count == 0 else "failed"
    details_json = json.dumps(details or {}, default=str, sort_keys=True)
    cur.execute(
        """
        INSERT INTO dq.check_results (
            batch_id,
            layer,
            check_name,
            status,
            severity,
            checked_count,
            failed_count,
            details
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (batch_id, layer, check_name) DO UPDATE
        SET status = EXCLUDED.status,
            severity = EXCLUDED.severity,
            checked_count = EXCLUDED.checked_count,
            failed_count = EXCLUDED.failed_count,
            details = EXCLUDED.details,
            created_at = NOW();
        """,
        (
            batch_id,
            layer,
            check_name,
            status,
            severity,
            checked_count,
            failed_count,
            details_json,
        ),
    )
    return status == "passed" or severity == "warning"


def _batch_counts(cur, batch_id) -> dict[str, int]:
    cur.execute(
        """
        SELECT extracted_count, silver_accepted_count, silver_rejected_count, gold_loaded_count
        FROM etl.batch_run
        WHERE batch_id = %s;
        """,
        (batch_id,),
    )
    row = cur.fetchone()
    if row is None:
        return {
            "extracted_count": 0,
            "silver_accepted_count": 0,
            "silver_rejected_count": 0,
            "gold_loaded_count": 0,
        }
    return {
        "extracted_count": int(row[0] or 0),
        "silver_accepted_count": int(row[1] or 0),
        "silver_rejected_count": int(row[2] or 0),
        "gold_loaded_count": int(row[3] or 0),
    }


def run_bronze_checks(cur, batch_id) -> list[bool]:
    results: list[bool] = []
    counts = _batch_counts(cur, batch_id)
    bronze_rows = _count(
        cur,
        "SELECT COUNT(*) FROM bronze.orders_raw WHERE batch_id = %s;",
        (batch_id,),
    )

    results.append(
        record_check_result(
            cur,
            batch_id,
            "bronze",
            "bronze_count_matches_batch_audit",
            "error",
            counts["extracted_count"],
            0 if bronze_rows == counts["extracted_count"] else abs(bronze_rows - counts["extracted_count"]),
            {
                "batch_extracted_count": counts["extracted_count"],
                "bronze_rows": bronze_rows,
            },
        )
    )

    duplicate_mongo_ids = _count(
        cur,
        """
        SELECT COALESCE(SUM(extra_rows), 0)
        FROM (
            SELECT COUNT(*) - 1 AS extra_rows
            FROM bronze.orders_raw
            WHERE batch_id = %s
            GROUP BY mongo_id
            HAVING COUNT(*) > 1
        ) duplicates;
        """,
        (batch_id,),
    )
    results.append(
        record_check_result(
            cur,
            batch_id,
            "bronze",
            "mongo_id_unique_within_batch",
            "error",
            bronze_rows,
            duplicate_mongo_ids,
        )
    )

    missing_order_ids = _count(
        cur,
        """
        SELECT COUNT(*)
        FROM bronze.orders_raw
        WHERE batch_id = %s
          AND NULLIF(BTRIM(payload ->> 'order_id'), '') IS NULL;
        """,
        (batch_id,),
    )
    results.append(
        record_check_result(
            cur,
            batch_id,
            "bronze",
            "source_order_id_present",
            "error",
            bronze_rows,
            missing_order_ids,
        )
    )

    missing_hashes = _count(
        cur,
        """
        SELECT COUNT(*)
        FROM bronze.orders_raw
        WHERE batch_id = %s
          AND NULLIF(BTRIM(payload_hash), '') IS NULL;
        """,
        (batch_id,),
    )
    results.append(
        record_check_result(
            cur,
            batch_id,
            "bronze",
            "payload_hash_present",
            "error",
            bronze_rows,
            missing_hashes,
        )
    )
    return results


def run_silver_checks(cur, batch_id) -> list[bool]:
    results: list[bool] = []
    bronze_rows = _count(
        cur,
        "SELECT COUNT(*) FROM bronze.orders_raw WHERE batch_id = %s;",
        (batch_id,),
    )
    clean_rows = _count(
        cur,
        "SELECT COUNT(*) FROM silver.orders_clean WHERE batch_id = %s;",
        (batch_id,),
    )
    rejected_rows = _count(
        cur,
        "SELECT COUNT(*) FROM silver.orders_rejected WHERE batch_id = %s;",
        (batch_id,),
    )

    accounted = clean_rows + rejected_rows
    results.append(
        record_check_result(
            cur,
            batch_id,
            "silver",
            "bronze_rows_accounted_in_silver",
            "error",
            bronze_rows,
            0 if accounted == bronze_rows else abs(bronze_rows - accounted),
            {
                "bronze_rows": bronze_rows,
                "silver_clean_rows": clean_rows,
                "silver_rejected_rows": rejected_rows,
            },
        )
    )

    duplicate_order_ids = _count(
        cur,
        """
        SELECT COALESCE(SUM(extra_rows), 0)
        FROM (
            SELECT COUNT(*) - 1 AS extra_rows
            FROM silver.orders_clean
            WHERE batch_id = %s
            GROUP BY order_id
            HAVING COUNT(*) > 1
        ) duplicates;
        """,
        (batch_id,),
    )
    results.append(
        record_check_result(
            cur,
            batch_id,
            "silver",
            "order_id_unique_within_batch",
            "error",
            clean_rows,
            duplicate_order_ids,
        )
    )

    missing_required = _count(
        cur,
        """
        SELECT COUNT(*)
        FROM silver.orders_clean
        WHERE batch_id = %s
          AND (
              NULLIF(BTRIM(order_id), '') IS NULL
              OR sold_at IS NULL
              OR NULLIF(BTRIM(customer_id), '') IS NULL
              OR NULLIF(BTRIM(customer_name), '') IS NULL
              OR NULLIF(BTRIM(product_id), '') IS NULL
              OR NULLIF(BTRIM(product_name), '') IS NULL
              OR NULLIF(BTRIM(retailer_id), '') IS NULL
              OR NULLIF(BTRIM(retailer_name), '') IS NULL
              OR NULLIF(BTRIM(street), '') IS NULL
              OR NULLIF(BTRIM(commune_ward), '') IS NULL
              OR NULLIF(BTRIM(province_city), '') IS NULL
              OR NULLIF(BTRIM(payment_type), '') IS NULL
              OR NULLIF(BTRIM(method_provider), '') IS NULL
          );
        """,
        (batch_id,),
    )
    results.append(
        record_check_result(
            cur,
            batch_id,
            "silver",
            "required_fields_not_null",
            "error",
            clean_rows,
            missing_required,
        )
    )

    invalid_ranges = _count(
        cur,
        """
        SELECT COUNT(*)
        FROM silver.orders_clean
        WHERE batch_id = %s
          AND (
              quantity <= 0
              OR price < 0
              OR discount < 0
              OR tax < 0
              OR discount > price * quantity
              OR quantity_in_stock < 0
              OR retailer_rating < 0
              OR retailer_rating > 5
          );
        """,
        (batch_id,),
    )
    results.append(
        record_check_result(
            cur,
            batch_id,
            "silver",
            "numeric_ranges_valid",
            "error",
            clean_rows,
            invalid_ranges,
        )
    )

    results.append(
        record_check_result(
            cur,
            batch_id,
            "silver",
            "rejected_rows_review",
            "warning",
            bronze_rows,
            rejected_rows,
            {"silver_rejected_rows": rejected_rows},
        )
    )
    return results


def run_gold_checks(cur, batch_id) -> list[bool]:
    results: list[bool] = []
    counts = _batch_counts(cur, batch_id)
    fact_rows = _count(
        cur,
        "SELECT COUNT(*) FROM dw.fact_sales WHERE batch_id = %s;",
        (batch_id,),
    )

    results.append(
        record_check_result(
            cur,
            batch_id,
            "gold",
            "gold_count_matches_batch_audit",
            "error",
            counts["gold_loaded_count"],
            0 if fact_rows == counts["gold_loaded_count"] else abs(fact_rows - counts["gold_loaded_count"]),
            {
                "batch_gold_loaded_count": counts["gold_loaded_count"],
                "gold_fact_rows": fact_rows,
            },
        )
    )

    missing_lineage = _count(
        cur,
        """
        SELECT COUNT(*)
        FROM dw.fact_sales
        WHERE batch_id = %s
          AND silver_id IS NULL;
        """,
        (batch_id,),
    )
    results.append(
        record_check_result(
            cur,
            batch_id,
            "gold",
            "fact_rows_have_silver_lineage",
            "error",
            fact_rows,
            missing_lineage,
        )
    )

    missing_facts = _count(
        cur,
        """
        SELECT COUNT(*)
        FROM silver.orders_clean s
        WHERE s.batch_id = %s
          AND NOT EXISTS (
              SELECT 1
              FROM dw.fact_sales f
              WHERE f.silver_id = s.silver_id
                AND f.batch_id = s.batch_id
          );
        """,
        (batch_id,),
    )
    results.append(
        record_check_result(
            cur,
            batch_id,
            "gold",
            "every_silver_row_loaded_to_fact",
            "error",
            counts["silver_accepted_count"],
            missing_facts,
        )
    )

    orphan_keys = _count(
        cur,
        """
        SELECT COUNT(*)
        FROM dw.fact_sales f
        WHERE f.batch_id = %s
          AND (
              NOT EXISTS (SELECT 1 FROM dw.dim_customer c WHERE c.customer_key = f.customer_key)
              OR NOT EXISTS (SELECT 1 FROM dw.dim_product p WHERE p.product_key = f.product_key)
              OR NOT EXISTS (SELECT 1 FROM dw.dim_retailer r WHERE r.retailer_key = f.retailer_key)
              OR NOT EXISTS (SELECT 1 FROM dw.dim_date d WHERE d.date_key = f.date_key)
              OR NOT EXISTS (SELECT 1 FROM dw.dim_address a WHERE a.address_key = f.address_key)
              OR NOT EXISTS (SELECT 1 FROM dw.dim_payment pay WHERE pay.payment_key = f.payment_key)
          );
        """,
        (batch_id,),
    )
    results.append(
        record_check_result(
            cur,
            batch_id,
            "gold",
            "fact_dimension_references_valid",
            "error",
            fact_rows,
            orphan_keys,
        )
    )
    return results


def run_reconciliation_checks(cur, batch_id) -> list[bool]:
    results: list[bool] = []
    silver_gross = _decimal(
        cur,
        """
        SELECT COALESCE(SUM(quantity * price), 0)::numeric
        FROM silver.orders_clean
        WHERE batch_id = %s;
        """,
        (batch_id,),
    )
    gold_gross = _decimal(
        cur,
        """
        SELECT COALESCE(SUM(quantity * price), 0)::numeric
        FROM dw.fact_sales
        WHERE batch_id = %s;
        """,
        (batch_id,),
    )
    results.append(
        record_check_result(
            cur,
            batch_id,
            "reconciliation",
            "silver_gold_gross_amount_match",
            "error",
            1,
            0 if silver_gross == gold_gross else 1,
            {"silver_gross_amount": silver_gross, "gold_gross_amount": gold_gross},
        )
    )

    silver_net = _decimal(
        cur,
        """
        SELECT COALESCE(SUM(quantity * price - discount + tax), 0)::numeric
        FROM silver.orders_clean
        WHERE batch_id = %s;
        """,
        (batch_id,),
    )
    gold_net = _decimal(
        cur,
        """
        SELECT COALESCE(SUM(quantity * price - discount + tax), 0)::numeric
        FROM dw.fact_sales
        WHERE batch_id = %s;
        """,
        (batch_id,),
    )
    results.append(
        record_check_result(
            cur,
            batch_id,
            "reconciliation",
            "silver_gold_net_amount_match",
            "error",
            1,
            0 if silver_net == gold_net else 1,
            {"silver_net_amount": silver_net, "gold_net_amount": gold_net},
        )
    )
    return results


def run_data_quality_checks(cur, batch_id) -> bool:
    results = []
    results.extend(run_bronze_checks(cur, batch_id))
    results.extend(run_silver_checks(cur, batch_id))
    results.extend(run_gold_checks(cur, batch_id))
    results.extend(run_reconciliation_checks(cur, batch_id))
    return all(results)
