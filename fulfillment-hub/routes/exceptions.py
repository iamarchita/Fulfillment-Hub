from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db import query_all, query_one, execute
from utils.auth import login_required

bp = Blueprint("exceptions", __name__)

STATUSES = ["Open", "In Progress", "Resolved"]
TYPES = ["Missing Stock", "Wrong Product/Variant", "Damaged Item", "Misplaced Box",
         "Missed Courier Pickup", "Delayed Processing"]


@bp.route("/exceptions")
@login_required
def list_exceptions():
    status = request.args.get("status", "")
    exc_type = request.args.get("type", "")
    where = []
    params = []
    if status:
        where.append("e.status = %s")
        params.append(status)
    if exc_type:
        where.append("e.exception_type = %s")
        params.append(exc_type)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = query_all(f"""
        SELECT e.*, o.customer_name, o.priority AS order_priority,
               ru.name AS reported_by_name, au.name AS assigned_to_name
        FROM exceptions e
        JOIN orders o ON o.order_id = e.order_id
        LEFT JOIN users ru ON ru.user_id = e.reported_by
        LEFT JOIN users au ON au.user_id = e.assigned_to
        {where_sql}
        ORDER BY FIELD(e.status,'Open','In Progress','Resolved'),
                 FIELD(e.priority,'Critical','High','Medium','Low'), e.reported_at DESC
    """, params)

    users = query_all("SELECT user_id, name, role FROM users")
    open_count = query_one("SELECT COUNT(*) c FROM exceptions WHERE status='Open'")["c"]
    in_progress_count = query_one("SELECT COUNT(*) c FROM exceptions WHERE status='In Progress'")["c"]

    return render_template(
        "exceptions.html", rows=rows, statuses=STATUSES, types=TYPES, users=users,
        status=status, exc_type=exc_type, open_count=open_count, in_progress_count=in_progress_count,
    )


@bp.route("/exceptions/<exception_id>/update", methods=["POST"])
@login_required
def update_exception(exception_id):
    exc = query_one("SELECT * FROM exceptions WHERE exception_id = %s", (exception_id,))
    if not exc:
        flash("Exception not found.", "error")
        return redirect(url_for("exceptions.list_exceptions"))

    new_status = request.form.get("status")
    assigned_to = request.form.get("assigned_to") or exc["assigned_to"]
    resolution = request.form.get("resolution", "").strip()

    if new_status not in STATUSES:
        flash("Invalid status.", "error")
        return redirect(url_for("exceptions.list_exceptions"))
    if new_status == "Resolved" and not resolution and not exc["resolution"]:
        flash("Please add a resolution note before marking this exception Resolved.", "error")
        return redirect(url_for("exceptions.list_exceptions"))

    execute(
        "UPDATE exceptions SET status=%s, assigned_to=%s, resolution=COALESCE(NULLIF(%s,''), resolution) "
        "WHERE exception_id=%s", (new_status, assigned_to, resolution, exception_id))

    if new_status == "Resolved":
        order = query_one("SELECT * FROM orders WHERE order_id = %s", (exc["order_id"],))
        if order and order["order_status"] == "Exception":
            # Resolving the exception returns the order to its last known working stage.
            from utils.helpers import set_order_status
            set_order_status(exc["order_id"], "Processed", session["user_id"],
                              "Exception resolved; order returned to processing.")
        flash(f"Exception {exception_id} resolved.", "success")
    else:
        flash(f"Exception {exception_id} updated to {new_status}.", "success")

    return redirect(url_for("exceptions.list_exceptions"))
