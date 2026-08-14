"""
app.py
-------
Main Flask application for SkillPalavar.

Routes are organized by role:
    - Public: /, /register, /login, /logout
    - Candidate: /candidate/*
    - Recruiter: /recruiter/*

All business logic (NLP, LLM, ML, scoring) lives in services/*.py — this
file only wires HTTP requests to those services and the database.
"""

import os
import traceback

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
import database
from routes.candidate import register_candidate_routes
from routes.recruiter import register_recruiter_routes


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    database.init_db(app)
    register_routes(app)
    register_error_handlers(app)
    return app


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_routes(app):

    # ---------------- Public ----------------

    @app.route("/")
    def index():
        if "user_id" in session:
            return redirect(url_for("dashboard_redirect"))
        return render_template("index.html")

    @app.route("/dashboard")
    def dashboard_redirect():
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session["role"] == "candidate":
            return redirect(url_for("candidate_dashboard"))
        return redirect(url_for("recruiter_dashboard"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            role = request.form.get("role", "candidate")

            if not name or not email or not password:
                flash("Please fill in all required fields.", "error")
                return render_template("register.html")
            if role not in ("candidate", "recruiter"):
                role = "candidate"
            if len(password) < 6:
                flash("Password must be at least 6 characters.", "error")
                return render_template("register.html")

            db = database.get_db()
            existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                flash("An account with that email already exists.", "error")
                return render_template("register.html")

            password_hash = generate_password_hash(password)
            cur = db.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (name, email, password_hash, role),
            )
            user_id = cur.lastrowid

            if role == "candidate":
                db.execute(
                    "INSERT INTO candidates (user_id, name, experience) VALUES (?, ?, 0)",
                    (user_id, name),
                )
            db.commit()

            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            db = database.get_db()
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

            if not user or not check_password_hash(user["password_hash"], password):
                flash("Invalid email or password.", "error")
                return render_template("login.html")

            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]

            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("dashboard_redirect"))

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    register_candidate_routes(app)
    register_recruiter_routes(app)


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="Page not found."), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("error.html", code=413,
                                message="File too large. Maximum resume size is 5 MB."), 413

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error(traceback.format_exc())
        return render_template("error.html", code=500,
                                message="Something went wrong on our end. Please try again."), 500


app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
