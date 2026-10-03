from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db import query_all, query_one, execute
from utils.helpers import next_id, set_order_status
from utils.auth import login_required

bp = Blueprint("packing", __name__)

PACKAGE_TYPES = ["Small Box", "Medium Box", "Large Box", "Envelope"]


@bp.route("/packing")
@login_required
def list_packing():
    rows = query_all("""
        SELECT o.order_id, o.customer_name, o.priority, o.order_status,
               pk.packing_id, pk.box_id, pk.package_type, pk.label_status, pk.status
        FROM orders o
        JOIN packing pk ON pk.order_id = o.order_id
        WHERE o.order_status = 'Packing'
        ORDER BY FIELD(o.priority,'Urgent','High','Normal')
    """)
    for r in rows:
        r["item_count"] = query_one(
            "SELECT COALESCE(SUM(quantity),0) c FROM order_items WHERE order_id = %s", (r["order_id"],)
        )["c"]
    return render_template("packing.html", rows=rows, package_types=PACKAGE_TYPES)


@bp.route("/packing/<order_id>/pack", methods=["POST"])
@login_required
def mark_packed(order_id):
    order = query_one("SELECT * FROM orders WHERE order_id = %s", (order_id,))
    if not order or order["order_status"] != "Packing":
        flash("Order is not ready to be packed.", "error")
        return redirect(url_for("packing.list_packing"))

    package_type = request.form.get("package_type") or "Medium Box"
    pack = query_one("SELECT * FROM packing WHERE order_id = %s", (order_id,))
    box_id = pack["box_id"] if pack and pack["box_id"] else f"BOX{order_id[3:]}"

    if pack:
        execute(
            "UPDATE packing SET box_id=%s, packed_by=%s, packed_at=NOW(), package_type=%s, "
            "label_status='Printed', status='Packed' WHERE order_id=%s",
            (box_id, session["name"], package_type, order_id),
        )
    else:
        pid = next_id("packing", "packing_id", "PACK", 4)
        execute(
            "INSERT INTO packing (packing_id, order_id, box_id, packed_by, packed_at, package_type, "
            "label_status, status) VALUES (%s,%s,%s,%s,NOW(),%s,'Printed','Packed')",
            (pid, order_id, box_id, session["name"], package_type),
        )

    set_order_status(order_id, "Staging", session["user_id"], "Packed and ready for staging.")

    staging_exists = query_one("SELECT 1 FROM staging WHERE order_id = %s", (order_id,))
    if not staging_exists:
        sid = next_id("staging", "staging_id", "STG", 4)
        execute(
            "INSERT INTO staging (staging_id, order_id, box_id, status, pickup_status) "
            "VALUES (%s,%s,%s,'Staged','Waiting')", (sid, order_id, box_id),
        )

    flash(f"Order {order_id} packed (Box {box_id}). Moved to Staging.", "success")
    return redirect(url_for("packing.list_packing"))
