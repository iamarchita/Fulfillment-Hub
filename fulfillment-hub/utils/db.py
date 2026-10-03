"""
Single reusable MySQL connection helper for Fulfillment Hub.
Uses mysql-connector-python directly (no ORM), parameterized queries only.
"""
import mysql.connector
from mysql.connector import Error as MySQLError
from flask import current_app, g


def get_db_connection():
    """Open a new MySQL connection using the app's configured credentials."""
    return mysql.connector.connect(
        host=current_app.config["DB_HOST"],
        user=current_app.config["DB_USER"],
        password=current_app.config["DB_PASSWORD"],
        database=current_app.config["DB_NAME"],
        port=current_app.config["DB_PORT"],
    )


def get_db():
    """Return a request-scoped connection, reused across the request."""
    if "db" not in g:
        g.db = get_db_connection()
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def query_all(sql, params=None):
    """Run a SELECT and return a list of dict rows."""
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params or ())
        return cur.fetchall()
    finally:
        cur.close()


def query_one(sql, params=None):
    """Run a SELECT and return a single dict row, or None."""
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=None):
    """Run an INSERT/UPDATE/DELETE, commit, and return the cursor's rowcount."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(sql, params or ())
        conn.commit()
        return cur.rowcount
    except MySQLError:
        conn.rollback()
        raise
    finally:
        cur.close()


def execute_many(statements):
    """
    Run several (sql, params) statements as a single transaction.
    Used when one user action must update several tables atomically
    (e.g. completing picking updates picking + orders + history).
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        for sql, params in statements:
            cur.execute(sql, params or ())
        conn.commit()
    except MySQLError:
        conn.rollback()
        raise
    finally:
        cur.close()
