"""
Shared operational logic used across route modules:
- the canonical fulfillment pipeline (for timelines + status transitions)
- ID generation for new operational records
- deadline / time-remaining calculations
- status-history + notification writers
"""
from datetime import datetime, date
from utils.db import query_one, execute

# Canonical fulfillment pipeline, in order. Used to render timelines and to
# stop a Delivered order from being pushed backwards.
PIPELINE = [
    "Order Received",
    "Processed",
    "Picking",
    "Packing",
    "Staging",
    "Ready for Pickup",
    "Shipped",
    "Delivered",
]

PRIORITY_RANK = {"Urgent": 0, "High": 1, "Normal": 2}


def pipeline_index(status):
    try:
        return PIPELINE.index(status)
    except ValueError:
        return -1


def can_advance(current_status, new_status):
    """Only allow moving forward in the pipeline (never backwards past Delivered)."""
    ci, ni = pipeline_index(current_status), pipeline_index(new_status)
    if ci == -1 or ni == -1:
        return True  # statuses outside the pipeline (e.g. custom) aren't blocked here
    if current_status == "Delivered":
        return False
    return ni >= ci


def next_id(table, id_col, prefix, width):
    """
    Generate the next sequential ID for a table, e.g. next_id('exceptions',
    'exception_id', 'EXC', 3) -> 'EXC026'. Looks at the current max suffix.
    """
    row = query_one(f"SELECT {id_col} FROM {table} ORDER BY {id_col} DESC LIMIT 1")
    if not row or not row[id_col]:
        n = 1
    else:
        digits = "".join(c for c in row[id_col] if c.isdigit())
        n = int(digits) + 1 if digits else 1
    return f"{prefix}{str(n).zfill(width)}"


def record_status_history(order_id, status, changed_by, notes="Status updated through fulfillment workflow"):
    hid = next_id("order_status_history", "history_id", "HIS", 5)
    execute(
        "INSERT INTO order_status_history (history_id, order_id, status, changed_at, changed_by, notes) "
        "VALUES (%s, %s, %s, NOW(), %s, %s)",
        (hid, order_id, status, changed_by, notes),
    )
    return hid


def create_notification(notification_type, order_id, severity, message, target_role):
    nid = next_id("notifications", "notification_id", "NOT", 3)
    execute(
        "INSERT INTO notifications (notification_id, notification_type, order_id, created_at, severity, message, status, target_role) "
        "VALUES (%s, %s, %s, NOW(), %s, %s, 'Unread', %s)",
        (nid, notification_type, order_id, severity, message, target_role),
    )
    return nid


def set_order_status(order_id, new_status, changed_by, notes=None):
    execute("UPDATE orders SET order_status = %s WHERE order_id = %s", (new_status, order_id))
    record_status_history(order_id, new_status, changed_by, notes or "Status updated through fulfillment workflow")


def time_remaining(deadline):
    """Return (label, is_overdue) for a deadline vs now."""
    if deadline is None:
        return "-", False
    now = datetime.now()
    if isinstance(deadline, date) and not isinstance(deadline, datetime):
        deadline = datetime.combine(deadline, datetime.min.time())
    delta = deadline - now
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 0:
        overdue_minutes = -total_minutes
        h, m = divmod(overdue_minutes, 60)
        return f"Overdue by {h}h {m}m", True
    h, m = divmod(total_minutes, 60)
    return f"{h}h {m}m", False


def recompute_stock_status(available_qty, reorder_level):
    if available_qty <= 0:
        return "Out of Stock"
    if available_qty <= reorder_level:
        return "Low Stock"
    return "Healthy"
