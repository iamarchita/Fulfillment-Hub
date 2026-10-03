from flask import Flask, render_template, session
from config import Config
from utils import db as db_utils


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db_utils.init_app(app)

    from routes import auth, dashboard, orders, inventory, transfers, picking, packing, shipping, exceptions, reports, settings

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(orders.bp)
    app.register_blueprint(inventory.bp)
    app.register_blueprint(transfers.bp)
    app.register_blueprint(picking.bp)
    app.register_blueprint(packing.bp)
    app.register_blueprint(shipping.bp)
    app.register_blueprint(exceptions.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(settings.bp)

    @app.context_processor
    def inject_notifications():
        if "user_id" not in session:
            return {}
        try:
            unread = db_utils.query_all(
                "SELECT * FROM notifications WHERE status='Unread' ORDER BY created_at DESC LIMIT 6"
            )
            unread_count = db_utils.query_one("SELECT COUNT(*) c FROM notifications WHERE status='Unread'")["c"]
            open_exc = db_utils.query_one("SELECT COUNT(*) c FROM exceptions WHERE status='Open'")["c"]
        except Exception:
            unread, unread_count, open_exc = [], 0, 0
        return {"nav_notifications": unread, "nav_unread_count": unread_count, "open_exceptions_nav": open_exc}

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html", message="That page could not be found."), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("500.html"), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
