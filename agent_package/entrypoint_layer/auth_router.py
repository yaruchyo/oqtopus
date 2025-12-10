from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from agent_package.system_layer.utils_auth import hash_password, check_password
from agent_package.system_layer.security import validate_password_strength
from agent_package.domain_layer.user_domain import User
from agent_package import db_connection
from datetime import datetime, timedelta, timezone

auth_router = Blueprint("auth_router", __name__)


def get_limiter():
    """Get the rate limiter from the current app context."""
    return getattr(current_app, "limiter", None)


@auth_router.route("/login", methods=["GET", "POST"])
def login():
    # Apply rate limiting - 5 login attempts per minute per IP
    limiter = get_limiter()
    if limiter:
        limiter.limit("50 per minute")(lambda: None)()

    if current_user.is_authenticated:
        return redirect(url_for("info_router.index"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # Basic input validation
        if not email or not password:
            flash("Email and password are required", "error")
            return render_template("login.html")

        user_data = db_connection.find_document("users", {"email": email})

        if user_data and check_password(user_data.get("password_hash"), password):
            user = User(user_data)
            login_user(user)

            # Only renew credits if last_reset_time is more than 24 hours ago (or never set)
            last_reset_str = user_data.get("last_reset_time")
            now_utc = datetime.now(timezone.utc)
            should_reset_credits = False

            if last_reset_str is None:
                # Never used credits before OR just registered - reset to 5
                should_reset_credits = True
            else:
                try:
                    last_reset = datetime.fromisoformat(last_reset_str)
                    if (now_utc - last_reset) > timedelta(hours=24):
                        should_reset_credits = True
                except ValueError:
                    # Invalid date format, reset credits
                    should_reset_credits = True

            if should_reset_credits:
                db_connection.update_document(
                    "users",
                    {"email": email},
                    {"requests_left": 5, "last_reset_time": None},
                )

            return redirect(url_for("info_router.index"))
        else:
            flash("Invalid email or password", "error")

    return render_template("login.html")


@auth_router.route("/register", methods=["GET", "POST"])
def register():
    # Apply rate limiting - 10 registration attempts per minute per IP
    limiter = get_limiter()
    if limiter:
        limiter.limit("10 per minute")(lambda: None)()

    if current_user.is_authenticated:
        return redirect(url_for("info_router.index"))

    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Basic input validation
        if not username or not email or not password:
            flash("All fields are required", "error")
            return render_template("register.html")

        # Check username length
        if len(username) < 3 or len(username) > 50:
            flash("Username must be between 3 and 50 characters", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template("register.html")

        # Validate password strength
        is_valid, error_message = validate_password_strength(password)
        if not is_valid:
            flash(error_message, "error")
            return render_template("register.html")

        existing_user = db_connection.find_document("users", {"email": email})
        if existing_user:
            flash("Email already registered", "error")
            return render_template("register.html")

        hashed_password = hash_password(password)
        new_user = {
            "username": username,
            "email": email,
            "password_hash": hashed_password,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "requests_left": 5,  # Initial credits for new users
            "last_reset_time": None,  # Will be set when first request is made
        }

        db_connection.insert_document("users", new_user)
        flash("Registration successful! Please login.", "success")
        return redirect(url_for("auth_router.login"))

    return render_template("register.html")


@auth_router.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth_router.login"))
