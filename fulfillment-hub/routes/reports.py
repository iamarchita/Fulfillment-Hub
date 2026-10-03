from flask import Blueprint, render_template
from utils.db import query_all, query_one
from utils.auth import login_required

bp = Blueprint("reports", __name__)


@bp.route("/reports")
@login_required
def index():
    order_metrics = query_one("""
        SELECT
            (SELECT COUNT(*) FROM orders) total,
            (SELECT COUNT(*) FROM orders WHERE order_status='Delivered') completed,
            (SELECT COUNT(*) FROM orders WHERE order_status<>'Delivered') pending,
            (SELECT COUNT(*) FROM orders WHERE priority_deadline<NOW() AND order_status<>'Delivered') AS `delayed`,
            (SELECT COUNT(*) FROM orders WHERE priority IN ('High','Urgent')) priority_count
    """)

    avg_fulfillment = query_one("""
        SELECT ROUND(AVG(TIMESTAMPDIFF(HOUR, o.order_date, sh.delivered_at)),1) avg_hours
        FROM orders o JOIN shipments sh ON sh.order_id = o.order_id
        WHERE sh.shipment_status='Delivered' AND sh.delivered_at IS NOT NULL
    """)["avg_hours"]

    by_stage = query_all("SELECT order_status stage, COUNT(*) c FROM orders GROUP BY order_status ORDER BY c DESC")
    stuck_by_stage = query_all("""
        SELECT order_status stage, COUNT(*) c FROM orders
        WHERE priority_deadline < NOW() AND order_status <> 'Delivered'
        GROUP BY order_status ORDER BY c DESC
    """)

    priority_on_time = query_one("""
        SELECT COUNT(*) c FROM orders o JOIN shipments sh ON sh.order_id=o.order_id
        WHERE o.priority IN ('High','Urgent') AND sh.shipment_status='Delivered'
        AND sh.delivered_at <= o.priority_deadline
    """)["c"]
    priority_overdue = query_one("""
        SELECT COUNT(*) c FROM orders o
        WHERE o.priority IN ('High','Urgent') AND o.priority_deadline < NOW() AND o.order_status <> 'Delivered'
    """)["c"]

    inv_low = query_one("SELECT COUNT(*) c FROM inventory WHERE stock_status='Low Stock'")["c"]
    inv_out = query_one("SELECT COUNT(*) c FROM inventory WHERE stock_status='Out of Stock'")["c"]
    inv_transfer_needed = query_one("""
        SELECT COUNT(*) c FROM inventory i
        WHERE i.warehouse_id='W001' AND i.stock_status IN ('Low Stock','Out of Stock')
        AND EXISTS (SELECT 1 FROM inventory s WHERE s.warehouse_id='W002' AND s.product_id=i.product_id AND s.available_qty>0)
    """)["c"]

    exc_open = query_one("SELECT COUNT(*) c FROM exceptions WHERE status='Open'")["c"]
    exc_resolved = query_one("SELECT COUNT(*) c FROM exceptions WHERE status='Resolved'")["c"]
    exc_by_type = query_all("SELECT exception_type type, COUNT(*) c FROM exceptions GROUP BY exception_type ORDER BY c DESC")

    courier_scheduled = query_one("SELECT COUNT(*) c FROM staging WHERE courier_id IS NOT NULL")["c"]
    courier_success = query_one("SELECT COUNT(*) c FROM staging WHERE pickup_status='Picked Up'")["c"]
    courier_missed = query_one("SELECT COUNT(*) c FROM staging WHERE pickup_status='Missed'")["c"]
    shipments_transit = query_one("SELECT COUNT(*) c FROM shipments WHERE shipment_status='In Transit'")["c"]
    shipments_delivered = query_one("SELECT COUNT(*) c FROM shipments WHERE shipment_status='Delivered'")["c"]

    return render_template(
        "reports.html",
        order_metrics=order_metrics, avg_fulfillment=avg_fulfillment,
        by_stage=by_stage, stuck_by_stage=stuck_by_stage,
        priority_on_time=priority_on_time, priority_overdue=priority_overdue,
        inv_low=inv_low, inv_out=inv_out, inv_transfer_needed=inv_transfer_needed,
        exc_open=exc_open, exc_resolved=exc_resolved, exc_by_type=exc_by_type,
        courier_scheduled=courier_scheduled, courier_success=courier_success, courier_missed=courier_missed,
        shipments_transit=shipments_transit, shipments_delivered=shipments_delivered,
    )
