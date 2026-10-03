from flask import Blueprint, render_template, redirect, url_for, session, request
from utils.db import query_all, query_one, execute
from utils.auth import login_required

bp = Blueprint("settings", __name__)


@bp.route("/settings")
@login_required
def index():
    user = query_one("SELECT user_id, name, role, email FROM users WHERE user_id = %s", (session["user_id"],))
    couriers = query_all("SELECT * FROM couriers ORDER BY courier_name")
    warehouses = query_all("SELECT * FROM warehouses ORDER BY warehouse_type")
    notifications = query_all("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 50")
    return render_template("settings.html", user=user, couriers=couriers, warehouses=warehouses,
                            notifications=notifications)


@bp.route("/notifications/<notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    execute("UPDATE notifications SET status='Read' WHERE notification_id = %s", (notification_id,))
    return redirect(request.referrer or url_for("dashboard.index"))


@bp.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_read():
    execute("UPDATE notifications SET status='Read' WHERE status='Unread'")
    return redirect(request.referrer or url_for("dashboard.index"))
