from flask import Blueprint, render_template
from utils.db import query_all, query_one
from utils.helpers import PIPELINE, time_remaining
from utils.auth import login_required

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@bp.route("/dashboard")
@login_required
def index():
    kpis = query_one("""
        SELECT
            (SELECT COUNT(*) FROM orders) AS total_orders,
            (SELECT COUNT(*) FROM orders WHERE order_status <> 'Delivered') AS pending_orders,
            (SELECT COUNT(*) FROM orders WHERE priority IN ('High','Urgent') AND order_status <> 'Delivered') AS priority_orders,
            (SELECT COUNT(*) FROM orders WHERE priority_deadline < NOW() AND order_status <> 'Delivered') AS delayed_orders,
            (SELECT COUNT(*) FROM orders WHERE order_status = 'Ready for Pickup') AS ready_pickup,
            (SELECT COUNT(*) FROM exceptions WHERE status = 'Open') AS open_exceptions,
            (SELECT COUNT(*) FROM inventory WHERE stock_status = 'Low Stock') AS low_stock,
            (SELECT COUNT(*) FROM inventory WHERE stock_status = 'Out of Stock') AS out_stock
    """)

    # Priority Orders Requiring Attention
    priority_orders = query_all("""
        SELECT order_id, customer_name, priority, order_status, priority_deadline
        FROM orders
        WHERE priority IN ('High','Urgent') AND order_status <> 'Delivered'
        ORDER BY priority_deadline ASC
        LIMIT 8
    """)
    for o in priority_orders:
        label, overdue = time_remaining(o["priority_deadline"])
        o["time_left"] = label
        o["overdue"] = overdue

    # Alerts
    approaching = query_one("""
        SELECT COUNT(*) c FROM orders
        WHERE priority IN ('High','Urgent') AND order_status <> 'Delivered'
        AND priority_deadline BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 6 HOUR)
    """)["c"]

    delayed_by_stage = query_all("""
        SELECT order_status, COUNT(*) c FROM orders
        WHERE priority_deadline < NOW() AND order_status <> 'Delivered'
        GROUP BY order_status ORDER BY c DESC
    """)

    missed_pickups = query_one("SELECT COUNT(*) c FROM staging WHERE pickup_status = 'Missed'")["c"]

    inv_risk_main = query_one("""
        SELECT COUNT(*) c FROM inventory
        WHERE warehouse_id = 'W001' AND stock_status IN ('Low Stock','Out of Stock')
    """)["c"]

    transfer_covered = query_one("""
        SELECT COUNT(*) c FROM inventory i
        WHERE i.warehouse_id = 'W001' AND i.stock_status IN ('Low Stock','Out of Stock')
        AND EXISTS (
            SELECT 1 FROM inventory s
            WHERE s.warehouse_id = 'W002' AND s.product_id = i.product_id AND s.available_qty > 0
        )
    """)["c"]

    open_exceptions = kpis["open_exceptions"]

    # Fulfillment pipeline counts (for the pipeline strip)
    stage_counts_raw = query_all("SELECT order_status, COUNT(*) c FROM orders GROUP BY order_status")
    stage_map = {r["order_status"]: r["c"] for r in stage_counts_raw}
    pipeline_counts = [{"stage": s, "count": stage_map.get(s, 0)} for s in PIPELINE]

    return render_template(
        "dashboard.html",
        kpis=kpis,
        priority_orders=priority_orders,
        approaching=approaching,
        delayed_by_stage=delayed_by_stage,
        missed_pickups=missed_pickups,
        inv_risk_main=inv_risk_main,
        transfer_covered=transfer_covered,
        open_exceptions=open_exceptions,
        pipeline_counts=pipeline_counts,
    )
