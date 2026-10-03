from flask import Blueprint, render_template, request
from utils.db import query_all
from utils.auth import login_required

bp = Blueprint("inventory", __name__)


@bp.route("/inventory")
@login_required
def list_inventory():
    search = request.args.get("q", "").strip()
    stock_filter = request.args.get("stock_status", "")
    category = request.args.get("category", "")

    where = []
    params = []
    if search:
        where.append("(p.product_name LIKE %s OR p.product_id LIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    if category:
        where.append("p.category = %s")
        params.append(category)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = query_all(f"""
        SELECT p.product_id, p.product_name, p.category, p.variant, p.reorder_level,
               MAX(CASE WHEN i.warehouse_id = 'W001' THEN i.available_qty END) AS main_qty,
               MAX(CASE WHEN i.warehouse_id = 'W001' THEN i.reserved_qty END) AS main_reserved,
               MAX(CASE WHEN i.warehouse_id = 'W001' THEN i.stock_status END) AS main_status,
               MAX(CASE WHEN i.warehouse_id = 'W002' THEN i.available_qty END) AS secondary_qty,
               MAX(CASE WHEN i.warehouse_id = 'W002' THEN i.stock_status END) AS secondary_status
        FROM products p
        JOIN inventory i ON i.product_id = p.product_id
        {where_sql}
        GROUP BY p.product_id, p.product_name, p.category, p.variant, p.reorder_level
        ORDER BY p.product_id
    """, params)

    if stock_filter:
        rows = [r for r in rows if r["main_status"] == stock_filter]

    categories = query_all("SELECT DISTINCT category FROM products ORDER BY category")

    low_count = sum(1 for r in rows if r["main_status"] == "Low Stock")
    out_count = sum(1 for r in rows if r["main_status"] == "Out of Stock")

    return render_template(
        "inventory.html", rows=rows, categories=categories, search=search,
        stock_filter=stock_filter, category=category, low_count=low_count, out_count=out_count,
    )
