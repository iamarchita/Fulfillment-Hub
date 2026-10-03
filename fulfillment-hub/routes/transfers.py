from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db import query_all, query_one, execute, execute_many
from utils.helpers import next_id, recompute_stock_status, create_notification
from utils.auth import login_required

bp = Blueprint("transfers", __name__)

VALID_STATUSES = ["Requested", "Approved", "In Transit", "Received", "Cancelled"]
FORWARD = {"Requested": "Approved", "Approved": "In Transit", "In Transit": "Received"}


@bp.route("/transfers")
@login_required
def list_transfers():
    status = request.args.get("status", "")
    where_sql = "WHERE t.status = %s" if status else ""
    params = [status] if status else []

    transfers = query_all(f"""
        SELECT t.*, p.product_name, fw.warehouse_name AS from_name, tw.warehouse_name AS to_name
        FROM warehouse_transfers t
        JOIN products p ON p.product_id = t.product_id
        JOIN warehouses fw ON fw.warehouse_id = t.from_warehouse_id
        JOIN warehouses tw ON tw.warehouse_id = t.to_warehouse_id
        {where_sql}
        ORDER BY FIELD(t.status,'Requested','Approved','In Transit','Received','Cancelled'), t.requested_at DESC
    """, params)

    products = query_all("SELECT product_id, product_name FROM products ORDER BY product_name")
    warehouses = query_all("SELECT warehouse_id, warehouse_name FROM warehouses")

    return render_template(
        "transfers.html", transfers=transfers, statuses=VALID_STATUSES,
        status=status, products=products, warehouses=warehouses,
    )


@bp.route("/transfers/create", methods=["POST"])
@login_required
def create_transfer():
    product_id = request.form.get("product_id")
    from_wh = request.form.get("from_warehouse_id")
    to_wh = request.form.get("to_warehouse_id")
    qty = request.form.get("quantity", "").strip()
    reason = request.form.get("reason", "").strip()

    if not (product_id and from_wh and to_wh and qty):
        flash("Please fill in all required transfer fields.", "error")
        return redirect(url_for("transfers.list_transfers"))
    if from_wh == to_wh:
        flash("Source and destination warehouse must be different.", "error")
        return redirect(url_for("transfers.list_transfers"))
    try:
        qty = int(qty)
        if qty <= 0:
            raise ValueError
    except ValueError:
        flash("Transfer quantity must be a positive number.", "error")
        return redirect(url_for("transfers.list_transfers"))

    tid = next_id("warehouse_transfers", "transfer_id", "TRF", 3)
    execute(
        "INSERT INTO warehouse_transfers (transfer_id, product_id, from_warehouse_id, to_warehouse_id, "
        "quantity, requested_at, status, requested_by, reason) VALUES (%s,%s,%s,%s,%s,NOW(),'Requested',%s,%s)",
        (tid, product_id, from_wh, to_wh, qty, session["user_id"], reason or "Stock balancing"),
    )
    flash(f"Transfer {tid} requested.", "success")
    return redirect(url_for("transfers.list_transfers"))


@bp.route("/transfers/<transfer_id>/status", methods=["POST"])
@login_required
def update_status(transfer_id):
    new_status = request.form.get("status")
    if new_status not in VALID_STATUSES:
        flash("Invalid transfer status.", "error")
        return redirect(url_for("transfers.list_transfers"))

    transfer = query_one("SELECT * FROM warehouse_transfers WHERE transfer_id = %s", (transfer_id,))
    if not transfer:
        flash("Transfer not found.", "error")
        return redirect(url_for("transfers.list_transfers"))
    if transfer["status"] in ("Received", "Cancelled"):
        flash(f"Transfer {transfer_id} is already {transfer['status']} and cannot be changed.", "error")
        return redirect(url_for("transfers.list_transfers"))

    if new_status == "Received":
        from_inv = query_one(
            "SELECT * FROM inventory WHERE warehouse_id=%s AND product_id=%s",
            (transfer["from_warehouse_id"], transfer["product_id"]),
        )
        to_inv = query_one(
            "SELECT * FROM inventory WHERE warehouse_id=%s AND product_id=%s",
            (transfer["to_warehouse_id"], transfer["product_id"]),
        )
        stmts = [("UPDATE warehouse_transfers SET status=%s, received_at=NOW() WHERE transfer_id=%s",
                   (new_status, transfer_id))]
        if from_inv:
            new_qty = max(from_inv["available_qty"] - transfer["quantity"], 0)
            new_status_from = recompute_stock_status(new_qty, from_inv["reorder_level"])
            stmts.append((
                "UPDATE inventory SET available_qty=%s, stock_status=%s WHERE inventory_id=%s",
                (new_qty, new_status_from, from_inv["inventory_id"]),
            ))
        if to_inv:
            new_qty = to_inv["available_qty"] + transfer["quantity"]
            new_status_to = recompute_stock_status(new_qty, to_inv["reorder_level"])
            stmts.append((
                "UPDATE inventory SET available_qty=%s, stock_status=%s WHERE inventory_id=%s",
                (new_qty, new_status_to, to_inv["inventory_id"]),
            ))
        execute_many(stmts)
        create_notification("Transfer received", None, "Low",
                             f"Transfer {transfer_id} received — inventory updated.", "Warehouse")
        flash(f"Transfer {transfer_id} marked Received. Inventory updated.", "success")
    else:
        execute("UPDATE warehouse_transfers SET status=%s WHERE transfer_id=%s", (new_status, transfer_id))
        flash(f"Transfer {transfer_id} marked {new_status}.", "success")

    return redirect(url_for("transfers.list_transfers"))
