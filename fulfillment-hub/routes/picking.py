from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db import query_all, query_one, execute, execute_many
from utils.helpers import next_id, set_order_status, time_remaining, create_notification
from utils.auth import login_required

bp = Blueprint("picking", __name__)


@bp.route("/picking")
@login_required
def queue():
    orders = query_all("""
        SELECT o.order_id, o.customer_name, o.priority, o.priority_deadline, o.warehouse_id,
               w.warehouse_name, o.order_status, pk.status AS pick_status
        FROM orders o
        JOIN warehouses w ON w.warehouse_id = o.warehouse_id
        LEFT JOIN picking pk ON pk.order_id = o.order_id
        WHERE o.order_status = 'Picking'
        ORDER BY FIELD(o.priority,'Urgent','High','Normal'), o.priority_deadline ASC
    """)
    for o in orders:
        label, overdue = time_remaining(o["priority_deadline"])
        o["time_left"] = label
        o["overdue"] = overdue
    return render_template("picking.html", orders=orders)


@bp.route("/picking/<order_id>")
@login_required
def picking_detail(order_id):
    order = query_one("""
        SELECT o.*, w.warehouse_name FROM orders o
        JOIN warehouses w ON w.warehouse_id = o.warehouse_id WHERE o.order_id = %s
    """, (order_id,))
    if not order:
        return render_template("404.html", message=f"Order {order_id} was not found."), 404

    items = query_all("""
        SELECT oi.*, p.product_name, p.variant FROM order_items oi
        JOIN products p ON p.product_id = oi.product_id WHERE oi.order_id = %s
    """, (order_id,))
    pick_record = query_one("SELECT * FROM picking WHERE order_id = %s", (order_id,))

    return render_template("picking_detail.html", order=order, items=items, pick_record=pick_record)


@bp.route("/picking/<order_id>/complete", methods=["POST"])
@login_required
def complete_picking(order_id):
    order = query_one("SELECT * FROM orders WHERE order_id = %s", (order_id,))
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("picking.queue"))
    if order["order_status"] != "Picking":
        flash(f"Order {order_id} is not currently in the Picking stage.", "error")
        return redirect(url_for("picking.queue"))

    product_ok = request.form.get("product_ok") == "on"
    variant_ok = request.form.get("variant_ok") == "on"
    qty_ok = request.form.get("qty_ok") == "on"
    picker = session["name"]

    existing = query_one("SELECT * FROM picking WHERE order_id = %s", (order_id,))
    pick_id = existing["picking_id"] if existing else next_id("picking", "picking_id", "PICK", 4)

    if product_ok and variant_ok and qty_ok:
        if existing:
            execute(
                "UPDATE picking SET picker=%s, completed_at=NOW(), status='Completed', verification_result='Verified' "
                "WHERE picking_id=%s", (picker, pick_id))
        else:
            execute(
                "INSERT INTO picking (picking_id, order_id, picker, started_at, completed_at, status, verification_result) "
                "VALUES (%s,%s,%s,NOW(),NOW(),'Completed','Verified')", (pick_id, order_id, picker))
        set_order_status(order_id, "Packing", session["user_id"], "Picking verified and completed.")

        pack_exists = query_one("SELECT 1 FROM packing WHERE order_id = %s", (order_id,))
        if not pack_exists:
            box_id = f"BOX{order_id[3:]}"
            new_pack_id = next_id("packing", "packing_id", "PACK", 4)
            execute(
                "INSERT INTO packing (packing_id, order_id, box_id, status, label_status) "
                "VALUES (%s,%s,%s,'Pending','Pending')", (new_pack_id, order_id, box_id))

        flash(f"Order {order_id} picking verified. Moved to Packing.", "success")
    else:
        issue_type = request.form.get("issue_type") or "Wrong Product/Variant"
        if existing:
            execute("UPDATE picking SET picker=%s, status='Blocked', verification_result=%s WHERE picking_id=%s",
                     (picker, issue_type, pick_id))
        else:
            execute(
                "INSERT INTO picking (picking_id, order_id, picker, started_at, status, verification_result) "
                "VALUES (%s,%s,%s,NOW(),'Blocked',%s)", (pick_id, order_id, picker, issue_type))

        exc_id = next_id("exceptions", "exception_id", "EXC", 3)
        desc_parts = []
        if not product_ok:
            desc_parts.append("product mismatch")
        if not variant_ok:
            desc_parts.append("variant mismatch")
        if not qty_ok:
            desc_parts.append("quantity mismatch")
        description = "Picking verification failed: " + ", ".join(desc_parts)
        execute(
            "INSERT INTO exceptions (exception_id, order_id, exception_type, description, reported_at, "
            "reported_by, assigned_to, priority, status) VALUES (%s,%s,%s,%s,NOW(),%s,%s,%s,'Open')",
            (exc_id, order_id, issue_type, description, session["user_id"], session["user_id"],
             "High" if order["priority"] in ("Urgent", "High") else "Medium"),
        )
        set_order_status(order_id, "Exception", session["user_id"], f"Picking blocked: {description}")
        create_notification("Picking exception", order_id, "High",
                             f"Order {order_id} blocked in picking: {description}", "Operations")
        flash(f"Verification failed for order {order_id}. Exception {exc_id} created.", "error")

    return redirect(url_for("picking.queue"))
