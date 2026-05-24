from __future__ import annotations

import html
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Iterable

import psycopg
from psycopg.rows import dict_row


def db_config() -> dict[str, Any]:
    return {
        "host": os.getenv("PGHOST", "postgres"),
        "port": int(os.getenv("PGPORT", "5432")),
        "dbname": os.getenv("POSTGRES_DB", "warehouse"),
        "user": os.getenv("POSTGRES_USER", "warehouse"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "connect_timeout": 5,
        "row_factory": dict_row,
    }


def fetch_one(cur: psycopg.Cursor[dict[str, Any]], query: str) -> dict[str, Any]:
    cur.execute(query)
    row = cur.fetchone()
    return dict(row) if row else {}


def fetch_all(cur: psycopg.Cursor[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    cur.execute(query)
    return [dict(row) for row in cur.fetchall()]


def fetch_dashboard_data() -> dict[str, Any]:
    try:
        with psycopg.connect(**db_config()) as conn:
            with conn.cursor() as cur:
                stats = fetch_one(
                    cur,
                    """
                    SELECT
                        COUNT(*) AS order_count,
                        COALESCE(SUM(quantity), 0) AS units_sold,
                        COALESCE(SUM((price - discount + tax) * quantity), 0)::numeric(14, 2) AS gross_sales,
                        COALESCE(AVG((price - discount + tax) * quantity), 0)::numeric(14, 2) AS avg_order_value
                    FROM dw.fact_sales;
                    """,
                )
                latest_batch = fetch_one(
                    cur,
                    """
                    SELECT
                        batch_id::text,
                        status,
                        extracted_count,
                        silver_accepted_count,
                        silver_rejected_count,
                        gold_loaded_count,
                        started_at,
                        finished_at,
                        CASE
                            WHEN finished_at IS NULL THEN NOW() - started_at
                            ELSE finished_at - started_at
                        END AS elapsed
                    FROM etl.batch_run
                    ORDER BY started_at DESC
                    LIMIT 1;
                    """,
                )
                daily_sales = fetch_all(
                    cur,
                    """
                    SELECT
                        d.full_date,
                        COUNT(*) AS orders,
                        COALESCE(SUM((f.price - f.discount + f.tax) * f.quantity), 0)::numeric(14, 2) AS sales
                    FROM dw.fact_sales f
                    JOIN dw.dim_date d ON d.date_key = f.date_key
                    GROUP BY d.full_date
                    ORDER BY d.full_date DESC
                    LIMIT 14;
                    """,
                )
                top_products = fetch_all(
                    cur,
                    """
                    SELECT
                        p.product_name,
                        COALESCE(p.product_category, '-') AS product_category,
                        COUNT(*) AS orders,
                        COALESCE(SUM(f.quantity), 0) AS units,
                        COALESCE(SUM((f.price - f.discount + f.tax) * f.quantity), 0)::numeric(14, 2) AS sales
                    FROM dw.fact_sales f
                    JOIN dw.dim_product p ON p.product_key = f.product_key
                    GROUP BY p.product_name, p.product_category
                    ORDER BY sales DESC, orders DESC
                    LIMIT 8;
                    """,
                )
                recent_orders = fetch_all(
                    cur,
                    """
                    SELECT
                        f.order_id,
                        d.full_date,
                        c.customer_name,
                        p.product_name,
                        r.retailer_name,
                        f.quantity,
                        ((f.price - f.discount + f.tax) * f.quantity)::numeric(14, 2) AS total,
                        f.loaded_at
                    FROM dw.fact_sales f
                    JOIN dw.dim_date d ON d.date_key = f.date_key
                    JOIN dw.dim_customer c ON c.customer_key = f.customer_key
                    JOIN dw.dim_product p ON p.product_key = f.product_key
                    JOIN dw.dim_retailer r ON r.retailer_key = f.retailer_key
                    ORDER BY f.loaded_at DESC
                    LIMIT 20;
                    """,
                )
                dq_results = fetch_all(
                    cur,
                    """
                    WITH latest AS (
                        SELECT batch_id
                        FROM etl.batch_run
                        ORDER BY started_at DESC
                        LIMIT 1
                    )
                    SELECT
                        layer,
                        check_name,
                        status,
                        severity,
                        checked_count,
                        failed_count,
                        COALESCE(details::text, '') AS details
                    FROM dq.check_results
                    WHERE batch_id = (SELECT batch_id FROM latest)
                    ORDER BY layer, check_name;
                    """,
                )
        return {
            "stats": stats,
            "latest_batch": latest_batch,
            "daily_sales": list(reversed(daily_sales)),
            "top_products": top_products,
            "recent_orders": recent_orders,
            "dq_results": dq_results,
            "error": None,
            "refreshed_at": datetime.now(timezone.utc),
        }
    except Exception as exc:  # pragma: no cover - shown on the rendered page
        return {
            "stats": {},
            "latest_batch": {},
            "daily_sales": [],
            "top_products": [],
            "recent_orders": [],
            "dq_results": [],
            "error": str(exc),
            "refreshed_at": datetime.now(timezone.utc),
        }


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def fmt_money(value: Any) -> str:
    if value is None:
        return "0.00"
    try:
        number = Decimal(value)
    except Exception:
        return esc(value)
    return f"{number:,.2f}"


def fmt_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return esc(value) if value else "-"


def fmt_duration(value: Any) -> str:
    if not value:
        return "-"
    if isinstance(value, timedelta):
        seconds = int(value.total_seconds())
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"
    return esc(value).split(".")[0]


def status_class(status: Any) -> str:
    normalized = str(status or "").lower()
    if normalized in {"success", "passed"}:
        return "success"
    if normalized in {"failed", "error"}:
        return "danger"
    if normalized in {"warning", "running"}:
        return "warning"
    return "muted-pill"


def metric(label: str, value: str, note: str) -> str:
    return f"""
    <article class="metric">
      <p>{esc(label)}</p>
      <strong>{value}</strong>
      <span>{esc(note)}</span>
    </article>
    """


def render_table(
    headers: Iterable[str],
    rows: list[dict[str, Any]],
    row_renderer: Callable[[dict[str, Any]], str],
    empty_text: str,
) -> str:
    if not rows:
        return f'<div class="empty">{esc(empty_text)}</div>'
    header_html = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body_html = "".join(row_renderer(row) for row in rows)
    return f"""
    <div class="table-wrap">
      <table>
        <thead><tr>{header_html}</tr></thead>
        <tbody>{body_html}</tbody>
      </table>
    </div>
    """


def render_daily_sales(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<div class="empty">No sales rows loaded yet.</div>'
    max_sales = max((float(row.get("sales") or 0) for row in rows), default=0) or 1
    bars = []
    for row in rows:
        sales = float(row.get("sales") or 0)
        width = max(2, (sales / max_sales) * 100) if sales else 0
        bars.append(
            f"""
            <div class="bar-row">
              <span class="bar-date">{fmt_datetime(row.get("full_date"))}</span>
              <div class="bar-track"><div class="bar-fill" style="width:{width:.1f}%"></div></div>
              <span class="bar-value">{fmt_money(row.get("sales"))}</span>
            </div>
            """
        )
    return "".join(bars)


def render_batch(batch: dict[str, Any]) -> str:
    if not batch:
        return '<div class="empty">No ETL batch has been recorded yet.</div>'
    return f"""
    <div class="batch-grid">
      <div><span>Status</span><strong class="pill {status_class(batch.get("status"))}">{esc(batch.get("status"))}</strong></div>
      <div><span>Extracted</span><strong>{fmt_int(batch.get("extracted_count"))}</strong></div>
      <div><span>Accepted</span><strong>{fmt_int(batch.get("silver_accepted_count"))}</strong></div>
      <div><span>Rejected</span><strong>{fmt_int(batch.get("silver_rejected_count"))}</strong></div>
      <div><span>Gold loaded</span><strong>{fmt_int(batch.get("gold_loaded_count"))}</strong></div>
      <div><span>Elapsed</span><strong>{fmt_duration(batch.get("elapsed"))}</strong></div>
    </div>
    <dl class="batch-meta">
      <dt>Batch ID</dt><dd>{esc(batch.get("batch_id"))}</dd>
      <dt>Started</dt><dd>{fmt_datetime(batch.get("started_at"))}</dd>
      <dt>Finished</dt><dd>{fmt_datetime(batch.get("finished_at"))}</dd>
    </dl>
    """


def render_dashboard(data: dict[str, Any]) -> str:
    stats = data["stats"]
    latest_batch = data["latest_batch"]
    error = data["error"]
    status = latest_batch.get("status") if latest_batch else "waiting"
    body_status = status_class(status)

    error_html = ""
    if error:
        error_html = f"""
        <section class="section error-section">
          <h2>Connection issue</h2>
          <p>{esc(error)}</p>
        </section>
        """

    dq_table = render_table(
        ["Layer", "Check", "Status", "Severity", "Checked", "Failed", "Details"],
        data["dq_results"],
        lambda row: f"""
        <tr>
          <td>{esc(row.get("layer"))}</td>
          <td>{esc(row.get("check_name"))}</td>
          <td><span class="pill {status_class(row.get("status"))}">{esc(row.get("status"))}</span></td>
          <td>{esc(row.get("severity"))}</td>
          <td>{fmt_int(row.get("checked_count"))}</td>
          <td>{fmt_int(row.get("failed_count"))}</td>
          <td class="details">{esc(row.get("details"))[:180]}</td>
        </tr>
        """,
        "No DQ results for the latest batch yet.",
    )

    product_table = render_table(
        ["Product", "Category", "Orders", "Units", "Sales"],
        data["top_products"],
        lambda row: f"""
        <tr>
          <td>{esc(row.get("product_name"))}</td>
          <td>{esc(row.get("product_category"))}</td>
          <td>{fmt_int(row.get("orders"))}</td>
          <td>{fmt_int(row.get("units"))}</td>
          <td class="money">{fmt_money(row.get("sales"))}</td>
        </tr>
        """,
        "No product sales loaded yet.",
    )

    recent_table = render_table(
        ["Order", "Date", "Customer", "Product", "Retailer", "Qty", "Total"],
        data["recent_orders"],
        lambda row: f"""
        <tr>
          <td>{esc(row.get("order_id"))}</td>
          <td>{fmt_datetime(row.get("full_date"))}</td>
          <td>{esc(row.get("customer_name"))}</td>
          <td>{esc(row.get("product_name"))}</td>
          <td>{esc(row.get("retailer_name"))}</td>
          <td>{fmt_int(row.get("quantity"))}</td>
          <td class="money">{fmt_money(row.get("total"))}</td>
        </tr>
        """,
        "No orders loaded yet.",
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="30">
  <title>Warehouse Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #182026;
      --muted: #65717d;
      --line: #dde3ea;
      --teal: #187c74;
      --blue: #285b9f;
      --amber: #946300;
      --red: #b3261e;
      --green-bg: #e7f5ef;
      --amber-bg: #fff3d6;
      --red-bg: #fde7e5;
      --blue-bg: #e9f1fb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 15px;
      line-height: 1.45;
    }}
    .page {{
      max-width: 1220px;
      margin: 0 auto;
      padding: 28px 20px 44px;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: flex-start;
      padding-bottom: 22px;
      border-bottom: 1px solid var(--line);
    }}
    h1, h2, h3, p {{ margin: 0; }}
    h1 {{
      font-size: 2rem;
      font-weight: 700;
      letter-spacing: 0;
    }}
    h2 {{
      font-size: 1.05rem;
      font-weight: 700;
      margin-bottom: 14px;
    }}
    .eyebrow {{
      color: var(--teal);
      font-size: .76rem;
      font-weight: 700;
      letter-spacing: 0;
      margin-bottom: 5px;
      text-transform: uppercase;
    }}
    .muted {{ color: var(--muted); margin-top: 6px; }}
    .refresh {{
      min-width: 220px;
      text-align: right;
      color: var(--muted);
      font-size: .88rem;
    }}
    .section {{
      margin-top: 22px;
      padding: 20px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 22px;
    }}
    .metric {{
      min-height: 118px;
      padding: 18px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .metric p {{
      color: var(--muted);
      font-size: .86rem;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .metric strong {{
      display: block;
      margin-top: 10px;
      font-size: 1.8rem;
      line-height: 1.15;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }}
    .metric span {{
      display: block;
      margin-top: 7px;
      color: var(--muted);
      font-size: .9rem;
    }}
    .grid-2 {{
      display: grid;
      grid-template-columns: 1fr 1.25fr;
      gap: 18px;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: 112px minmax(120px, 1fr) 120px;
      align-items: center;
      gap: 12px;
      min-height: 32px;
      margin: 8px 0;
    }}
    .bar-date, .bar-value {{
      color: var(--muted);
      font-size: .9rem;
      white-space: nowrap;
    }}
    .bar-value {{
      color: var(--ink);
      font-variant-numeric: tabular-nums;
      text-align: right;
    }}
    .bar-track {{
      height: 12px;
      background: #edf1f5;
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      min-width: 0;
      background: var(--teal);
      border-radius: inherit;
    }}
    .batch-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .batch-grid div {{
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfd;
    }}
    .batch-grid span, .batch-meta dt {{
      display: block;
      color: var(--muted);
      font-size: .78rem;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .batch-grid strong {{
      display: block;
      margin-top: 5px;
      font-size: 1rem;
      overflow-wrap: anywhere;
    }}
    .batch-meta {{
      display: grid;
      grid-template-columns: 80px minmax(0, 1fr);
      gap: 8px 12px;
      margin: 16px 0 0;
    }}
    .batch-meta dd {{
      margin: 0;
      overflow-wrap: anywhere;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 3px 9px;
      border-radius: 999px;
      font-size: .82rem;
      font-weight: 700;
      text-transform: capitalize;
    }}
    .success {{ color: #12603d; background: var(--green-bg); }}
    .warning {{ color: var(--amber); background: var(--amber-bg); }}
    .danger {{ color: var(--red); background: var(--red-bg); }}
    .muted-pill {{ color: var(--blue); background: var(--blue-bg); }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      min-width: 760px;
      border-collapse: collapse;
      background: var(--panel);
    }}
    th, td {{
      padding: 11px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: .78rem;
      font-weight: 700;
      text-transform: uppercase;
      background: #f9fafb;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .money {{
      font-variant-numeric: tabular-nums;
      text-align: right;
      white-space: nowrap;
    }}
    .details {{
      max-width: 260px;
      color: var(--muted);
      overflow-wrap: anywhere;
    }}
    .empty {{
      padding: 18px;
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 8px;
      background: #fbfcfd;
    }}
    .error-section {{
      border-color: #f1b4ae;
      background: #fff7f6;
    }}
    .error-section p {{
      color: var(--red);
      overflow-wrap: anywhere;
    }}
    @media (max-width: 900px) {{
      header, .grid-2 {{ grid-template-columns: 1fr; display: grid; }}
      .refresh {{ min-width: 0; text-align: left; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 620px) {{
      .page {{ padding: 20px 12px 32px; }}
      .metrics {{ grid-template-columns: 1fr; }}
      .section {{ padding: 14px; }}
      .bar-row {{
        grid-template-columns: 1fr;
        gap: 6px;
        margin: 14px 0;
      }}
      .bar-value {{ text-align: left; }}
      .batch-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <header>
      <div>
        <p class="eyebrow">Data Warehouse</p>
        <h1>Sales Dashboard</h1>
        <p class="muted">Gold sales, latest ETL status, and data quality checks from PostgreSQL.</p>
      </div>
      <div class="refresh">
        <span class="pill {body_status}">{esc(status)}</span>
        <p class="muted">Refreshed {fmt_datetime(data["refreshed_at"])}</p>
      </div>
    </header>

    {error_html}

    <section class="metrics" aria-label="Warehouse metrics">
      {metric("Orders", fmt_int(stats.get("order_count")), "Rows in dw.fact_sales")}
      {metric("Units sold", fmt_int(stats.get("units_sold")), "Total quantity")}
      {metric("Gross sales", fmt_money(stats.get("gross_sales")), "Price minus discount plus tax")}
      {metric("Avg order value", fmt_money(stats.get("avg_order_value")), "Average fact row value")}
    </section>

    <section class="section">
      <h2>Sales by Day</h2>
      {render_daily_sales(data["daily_sales"])}
    </section>

    <div class="grid-2">
      <section class="section">
        <h2>Latest ETL Batch</h2>
        {render_batch(latest_batch)}
      </section>

      <section class="section">
        <h2>Latest Data Quality Results</h2>
        {dq_table}
      </section>
    </div>

    <section class="section">
      <h2>Top Products</h2>
      {product_table}
    </section>

    <section class="section">
      <h2>Recent Orders</h2>
      {recent_table}
    </section>
  </div>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
            return

        if self.path not in {"/", "/index.html"}:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"not found")
            return

        data = fetch_dashboard_data()
        page = render_dashboard(data).encode("utf-8")
        self.send_response(503 if data["error"] else 200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> None:
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"Dashboard listening on 0.0.0.0:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
