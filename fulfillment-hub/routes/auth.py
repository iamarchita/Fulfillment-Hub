from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from utils.db import query_one

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "error")
            return render_template("login.html")

        try:
            user = query_one("SELECT * FROM users WHERE email = %s", (email,))
        except Exception:
            flash("The system is temporarily unavailable. Please try again shortly.", "error")
            return render_template("login.html")

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["user_id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard.index"))

        flash("Incorrect email or password.", "error")
        return render_template("login.html")

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
