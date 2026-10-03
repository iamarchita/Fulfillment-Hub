from flask import Blueprint, render_template, request
from utils.db import query_all, query_one
from utils.helpers import PIPELINE, pipeline_index, time_remaining
from utils.auth import login_required

bp = Blueprint("orders", __name__)

PAGE_SIZE = 25


@bp.route("/orders")
@login_required
def list_orders():
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")
    warehouse = request.args.get("warehouse", "")
    date_from = request.args.get("date_from", "")
    page = max(int(request.args.get("page", 1) or 1), 1)

    where = []
    params = []
    if search:
        where.append("(o.order_id LIKE %s OR o.customer_name LIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    if status:
        where.append("o.order_status = %s")
        params.append(status)
    if priority:
        where.append("o.priority = %s")
        params.append(priority)
    if warehouse:
        where.append("o.warehouse_id = %s")
        params.append(warehouse)
    if date_from:
        where.append("DATE(o.order_date) = %s")
        params.append(date_from)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = query_one(f"SELECT COUNT(*) c FROM orders o {where_sql}", params)["c"]
    total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page = min(page, total_pages)
    offset = (page - 1) * PAGE_SIZE

    orders = query_all(f"""
        SELECT o.order_id, o.customer_name, o.order_date, o.priority, o.priority_deadline,
               o.warehouse_id, w.warehouse_name, o.order_status, o.total_amount
        FROM orders o
        JOIN warehouses w ON w.warehouse_id = o.warehouse_id
        {where_sql}
        ORDER BY FIELD(o.priority,'Urgent','High','Normal'), o.priority_deadline ASC
        LIMIT %s OFFSET %s
    """, params + [PAGE_SIZE, offset])

    for o in orders:
        label, overdue = time_remaining(o["priority_deadline"])
        o["time_left"] = label
        o["overdue"] = overdue

    warehouses = query_all("SELECT warehouse_id, warehouse_name FROM warehouses")
    statuses = PIPELINE + ["Exception"]

    return render_template(
        "orders.html", orders=orders, warehouses=warehouses, statuses=statuses,
        search=search, status=status, priority=priority, warehouse=warehouse,
        date_from=date_from, page=page, total_pages=total_pages, total=total,
    )


@bp.route("/orders/<order_id>")
@login_required
def order_detail(order_id):
    order = query_one("""
        SELECT o.*, w.warehouse_name FROM orders o
        JOIN warehouses w ON w.warehouse_id = o.warehouse_id
        WHERE o.order_id = %s
    """, (order_id,))
    if not order:
        return render_template("404.html", message=f"Order {order_id} was not found."), 404

    items = query_all("""
        SELECT oi.*, p.product_name, p.category, p.variant
        FROM order_items oi JOIN products p ON p.product_id = oi.product_id
        WHERE oi.order_id = %s
    """, (order_id,))

    history = query_all(
        "SELECT * FROM order_status_history WHERE order_id = %s ORDER BY changed_at ASC",
        (order_id,)
    )

    exception = query_one(
        "SELECT * FROM exceptions WHERE order_id = %s ORDER BY reported_at DESC LIMIT 1",
        (order_id,)
    )

    picking = query_one("SELECT * FROM picking WHERE order_id = %s", (order_id,))
    packing = query_one("SELECT * FROM packing WHERE order_id = %s", (order_id,))
    staging = query_one("""
        SELECT s.*, c.courier_name FROM staging s
        LEFT JOIN couriers c ON c.courier_id = s.courier_id
        WHERE s.order_id = %s
    """, (order_id,))
    shipment = query_one("""
        SELECT sh.*, c.courier_name FROM shipments sh
        LEFT JOIN couriers c ON c.courier_id = sh.courier_id
        WHERE sh.order_id = %s
    """, (order_id,))

    label, overdue = time_remaining(order["priority_deadline"])
    current_idx = pipeline_index(order["order_status"])

    return render_template(
        "order_detail.html", order=order, items=items, history=history,
        exception=exception, picking=picking, packing=packing, staging=staging,
        shipment=shipment, time_left=label, overdue=overdue,
        pipeline=PIPELINE, current_idx=current_idx,
    )
