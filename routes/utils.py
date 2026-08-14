"""
routes/utils.py
-----------------
Small helpers shared across candidate and recruiter route modules.
"""

from functools import wraps
from flask import session, flash, redirect, url_for
from config import Config


def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("You do not have access to that page.", "error")
                return redirect(url_for("dashboard_redirect"))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS
