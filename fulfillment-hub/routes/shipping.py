from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db import query_all, query_one, execute
from utils.helpers import next_id, set_order_status, create_notification
from utils.auth import login_required

bp = Blueprint("shipping", __name__)


@bp.route("/staging")
@login_required
def list_staging():
    rows = query_all("""
        SELECT o.order_id, o.customer_name, o.priority, o.order_status,
               s.staging_id, s.box_id, s.staging_location, s.courier_id, s.scheduled_pickup,
               s.pickup_status, s.status AS staging_status, c.courier_name,
               sh.shipment_status, sh.tracking_number
        FROM orders o
        JOIN staging s ON s.order_id = o.order_id
        LEFT JOIN couriers c ON c.courier_id = s.courier_id
        LEFT JOIN shipments sh ON sh.order_id = o.order_id
        WHERE o.order_status IN ('Staging','Ready for Pickup','Shipped')
        ORDER BY FIELD(o.priority,'Urgent','High','Normal')
    """)
    couriers = query_all("SELECT * FROM couriers ORDER BY courier_name")
    return render_template("shipping.html", rows=rows, couriers=couriers)


@bp.route("/staging/<order_id>/assign", methods=["POST"])
@login_required
def assign_courier(order_id):
    order = query_one("SELECT * FROM orders WHERE order_id = %s", (order_id,))
    if not order or order["order_status"] != "Staging":
        flash("Order is not in Staging.", "error")
        return redirect(url_for("shipping.list_staging"))

    location = request.form.get("staging_location", "").strip()
    courier_id = request.form.get("courier_id")
    scheduled_pickup = request.form.get("scheduled_pickup")

    if not (location and courier_id and scheduled_pickup):
        flash("Please provide staging location, courier and scheduled pickup time.", "error")
        return redirect(url_for("shipping.list_staging"))

    execute(
        "UPDATE staging SET staging_location=%s, courier_id=%s, scheduled_pickup=%s, staged_at=COALESCE(staged_at, NOW()) "
        "WHERE order_id=%s", (location, courier_id, scheduled_pickup, order_id))
    set_order_status(order_id, "Ready for Pickup", session["user_id"], f"Staged at {location}, courier assigned.")
    flash(f"Order {order_id} staged and courier assigned.", "success")
    return redirect(url_for("shipping.list_staging"))


@bp.route("/staging/<order_id>/pickup", methods=["POST"])
@login_required
def courier_pickup(order_id):
    action = request.form.get("action")
    staging = query_one("SELECT * FROM staging WHERE order_id = %s", (order_id,))
    order = query_one("SELECT * FROM orders WHERE order_id = %s", (order_id,))
    if not staging or not order:
        flash("Staging record not found.", "error")
        return redirect(url_for("shipping.list_staging"))

    if action == "missed":
        execute("UPDATE staging SET pickup_status='Missed' WHERE order_id=%s", (order_id,))
        exc_id = next_id("exceptions", "exception_id", "EXC", 3)
        execute(
            "INSERT INTO exceptions (exception_id, order_id, exception_type, description, reported_at, "
            "reported_by, assigned_to, priority, status) VALUES (%s,%s,'Missed Courier Pickup', "
            "'Courier did not collect package within pickup window', NOW(), %s, %s, %s, 'Open')",
            (exc_id, order_id, session["user_id"], session["user_id"],
             "High" if order["priority"] in ("Urgent", "High") else "Medium"),
        )
        create_notification("Courier pickup missed", order_id, "High",
                             f"Missed pickup for order {order_id}. Reschedule or escalate.", "Operations")
        flash(f"Pickup marked Missed for {order_id}. Exception {exc_id} created.", "error")
        return redirect(url_for("shipping.list_staging"))

    if order["order_status"] != "Ready for Pickup":
        flash("Order is not ready for courier pickup.", "error")
        return redirect(url_for("shipping.list_staging"))

    execute("UPDATE staging SET pickup_status='Picked Up' WHERE order_id=%s", (order_id,))

    shipment = query_one("SELECT * FROM shipments WHERE order_id = %s", (order_id,))
    tracking = f"TRK{order_id[3:].zfill(5)}{staging['courier_id'] or ''}"
    if shipment:
        execute(
            "UPDATE shipments SET courier_id=%s, tracking_number=%s, shipped_at=NOW(), "
            "expected_delivery=DATE_ADD(CURDATE(), INTERVAL 3 DAY), shipment_status='In Transit' WHERE order_id=%s",
            (staging["courier_id"], tracking, order_id))
    else:
        sid = next_id("shipments", "shipment_id", "SHP", 4)
        execute(
            "INSERT INTO shipments (shipment_id, order_id, courier_id, tracking_number, shipped_at, "
            "expected_delivery, shipment_status) VALUES (%s,%s,%s,%s,NOW(),DATE_ADD(CURDATE(), INTERVAL 3 DAY),'In Transit')",
            (sid, order_id, staging["courier_id"], tracking))

    set_order_status(order_id, "Shipped", session["user_id"], "Courier picked up the shipment.")
    flash(f"Order {order_id} picked up by courier and marked Shipped.", "success")
    return redirect(url_for("shipping.list_staging"))


@bp.route("/staging/<order_id>/deliver", methods=["POST"])
@login_required
def mark_delivered(order_id):
    order = query_one("SELECT * FROM orders WHERE order_id = %s", (order_id,))
    if not order or order["order_status"] != "Shipped":
        flash("Order is not currently Shipped.", "error")
        return redirect(url_for("shipping.list_staging"))
    execute("UPDATE shipments SET shipment_status='Delivered', delivered_at=NOW() WHERE order_id=%s", (order_id,))
    set_order_status(order_id, "Delivered", session["user_id"], "Delivered to customer.")
    flash(f"Order {order_id} marked Delivered.", "success")
    return redirect(url_for("shipping.list_staging"))


@bp.route("/staging/<order_id>/label")
@login_required
def shipping_label(order_id):
    order = query_one("SELECT * FROM orders WHERE order_id = %s", (order_id,))
    staging = query_one("""
        SELECT s.*, c.courier_name, c.service_type FROM staging s
        LEFT JOIN couriers c ON c.courier_id = s.courier_id WHERE s.order_id = %s
    """, (order_id,))
    shipment = query_one("SELECT * FROM shipments WHERE order_id = %s", (order_id,))
    if not order:
        return render_template("404.html", message=f"Order {order_id} was not found."), 404
    return render_template("label.html", order=order, staging=staging, shipment=shipment)
