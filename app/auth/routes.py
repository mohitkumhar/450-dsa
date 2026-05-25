import re
import secrets

from bson import ObjectId
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import UserMixin, current_user, login_required, login_user, logout_user

from app.extensions import bcrypt, db, github, google, login_manager
from app.utils import utc_now


auth_bp = Blueprint("auth", __name__)
GOOGLE_OAUTH_NONCE_SESSION_KEY = "google_oauth_nonce"
COMMON_WEAK_PASSWORDS = {
    "12345678",
    "123456789",
    "password",
    "password1",
    "qwerty123",
    "admin123",
    "letmein",
    "welcome1",
}


def resolve_oauth_user(provider_field, provider_id, name, email=None):
    """Find, link, or create an OAuth-backed user record.

    Returns a tuple of `(user_doc, action)` where action is one of
    `existing`, `linked`, or `created`.
    """
    user_doc = db.user.find_one({provider_field: provider_id})
    if user_doc:
        return user_doc, "existing"

    if email:
        user_doc = db.user.find_one({"email": email})

    if user_doc:
        db.user.update_one({"_id": user_doc["_id"]}, {"$set": {provider_field: provider_id}})
        user_doc[provider_field] = provider_id
        return user_doc, "linked"

    result = db.user.insert_one(
        {
            "name": name,
            "email": email,
            provider_field: provider_id,
            "progress": {},
            "is_admin": False,
            "created_at": utc_now(),
        }
    )
    user_doc = db.user.find_one({"_id": result.inserted_id})
    return user_doc, "created"


def validate_registration_password(password, confirm_password):
    """Return user-facing validation errors for local password registration."""
    password = password or ""
    confirm_password = confirm_password or ""
    errors = []

    if password != confirm_password:
        errors.append("Password and confirm password must match.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must include at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        errors.append("Password must include at least one lowercase letter.")
    if not re.search(r"\d", password):
        errors.append("Password must include at least one number.")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("Password must include at least one special character.")
    if password.lower() in COMMON_WEAK_PASSWORDS:
        errors.append("Password is too common. Please choose a stronger password.")

    return errors


class UserWrapper(UserMixin):
    """Wrap a pymongo user dict for flask-login compatibility."""

    def __init__(self, user_doc):
        self._doc = user_doc or {}

    def get_id(self):
        return str(self._doc["_id"])

    @property
    def id(self):
        return self._doc.get("_id")

    @property
    def progress(self):
        return self._doc.get("progress", {})

    @property
    def is_admin(self):
        return bool(self._doc.get("is_admin", False))

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._doc.get(name)

    def reload(self):
        self._doc = db.user.find_one({"_id": self._doc["_id"]}) or self._doc
        return self


@login_manager.user_loader
def load_user(user_id):
    try:
        doc = db.user.find_one({"_id": ObjectId(user_id)})
        return UserWrapper(doc) if doc else None
    except Exception:
        return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("tracker.index"))
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user_doc = db.user.find_one({"email": email})
        if user_doc and user_doc.get("password") and bcrypt.check_password_hash(user_doc["password"], password):
            login_user(UserWrapper(user_doc))
            flash(f"Welcome back, {user_doc.get('name', 'User')}! 👋", "success")
            return redirect(url_for("tracker.index"))
        flash("Login unsuccessful. Please check email and password.", "danger")
    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("tracker.index"))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        password_errors = validate_registration_password(password, confirm_password)
        if password_errors:
            flash(" ".join(password_errors), "danger")
            return redirect(url_for("auth.register"))

        if not name:
            flash("Name is required", "danger")
            return redirect(url_for("auth.register"))

        existing_user = db.user.find_one({"email": email})
        if existing_user:
            flash("Email already registered", "danger")
            return redirect(url_for("auth.register"))

        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        try:
            db.user.insert_one(
                {
                    "name": name,
                    "email": email,
                    "password": hashed_password,
                    "progress": {},
                    "is_admin": False,
                    "created_at": utc_now(),
                }
            )
            flash("Your account has been created! You can now log in.", "success")
            return redirect(url_for("auth.login"))
        except Exception:
            flash("An error occurred during registration.", "danger")
    return render_template("register.html")


@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/delete_account", methods=["POST"])
@login_required
def delete_account():
    # CSRF check — consume token immediately (single-use)
    token = request.form.get("csrf_token", "")
    expected = session.pop("delete_csrf_token", None)
    if not token or not expected or token != expected:
        abort(403)

    user_doc = db.user.find_one({"_id": current_user.id})
    if not user_doc:
        logout_user()
        return redirect(url_for("auth.login"))

    # Password accounts require password confirmation
    if user_doc.get("password"):
        password = request.form.get("password", "")
        if not password or not bcrypt.check_password_hash(user_doc["password"], password):
            flash("Incorrect password. Account not deleted.", "danger")
            return redirect(url_for("profile.profile"))

    user_id = current_user.id
    logout_user()
    db.user.delete_one({"_id": user_id})
    flash("Your account has been permanently deleted.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/delete_account/token", methods=["GET"])
@login_required
def delete_account_token():
    """Generate and return a CSRF token for the delete account form."""
    token = secrets.token_hex(32)
    session["delete_csrf_token"] = token
    from flask import jsonify
    user_doc = db.user.find_one({"_id": current_user.id}, {"password": 1}) or {}
    return jsonify({"csrf_token": token, "is_oauth": not bool(user_doc.get("password"))})


@auth_bp.route("/login/github")
def login_github():
    redirect_uri = url_for("auth.authorize_github", _external=True)
    return github.authorize_redirect(redirect_uri)


@auth_bp.route("/login/github/authorize")
def authorize_github():
    try:
        token = github.authorize_access_token()
    except Exception:
        current_app.logger.exception("GitHub OAuth token exchange failed")
        flash("GitHub sign-in is temporarily unavailable. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    if not token:
        return "GitHub authorization failed", 400

    try:
        response = github.get("user")
    except Exception:
        current_app.logger.exception("GitHub OAuth user fetch failed")
        flash("GitHub sign-in is temporarily unavailable. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    if not response.ok:
        return "Failed to fetch GitHub user", 400

    try:
        user_info = response.json()
    except Exception:
        current_app.logger.exception("GitHub OAuth user payload parsing failed")
        flash("GitHub sign-in is temporarily unavailable. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    github_id = str(user_info["id"])

    email = None
    try:
        response_emails = github.get("user/emails")
        if response_emails.status_code == 200:
            for email_item in response_emails.json():
                if email_item["primary"] and email_item["verified"]:
                    email = email_item["email"]
                    break
    except Exception:
        current_app.logger.exception("GitHub OAuth email lookup failed")

    user_doc, action = resolve_oauth_user(
        "github_id",
        github_id,
        user_info.get("name", user_info.get("login", "GitHub User")),
        email=email,
    )
    if action == "linked":
        flash("Linked GitHub to your account! Welcome back!", "success")
    elif action == "created":
        flash("Welcome! Your GitHub account has been connected. 🎉", "success")

    login_user(UserWrapper(user_doc))
    return redirect(url_for("tracker.index"))


@auth_bp.route("/login/google")
def login_google():
    redirect_uri = url_for("auth.authorize_google", _external=True)
    nonce = secrets.token_urlsafe(16)
    session[GOOGLE_OAUTH_NONCE_SESSION_KEY] = nonce
    return google.authorize_redirect(redirect_uri, nonce=nonce)


@auth_bp.route("/login/google/authorize")
def authorize_google():
    nonce = session.pop(GOOGLE_OAUTH_NONCE_SESSION_KEY, None)
    if not nonce:
        return "Google OAuth nonce missing", 400

    try:
        token = google.authorize_access_token()
    except Exception:
        current_app.logger.exception("Google OAuth token exchange failed")
        flash("Google sign-in is temporarily unavailable. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    try:
        user_info = google.parse_id_token(token, nonce=nonce)
    except Exception:
        current_app.logger.exception("Google OAuth ID token parsing failed")
        flash("Google sign-in is temporarily unavailable. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    if not user_info:
        try:
            user_info = google.userinfo()
        except Exception:
            current_app.logger.exception("Google OAuth userinfo fetch failed")
            flash("Google sign-in is temporarily unavailable. Please try again.", "danger")
            return redirect(url_for("auth.login"))

    if not user_info:
        return "Failed to fetch Google user info", 400

    google_id = user_info["sub"]
    email = user_info.get("email")

    user_doc, action = resolve_oauth_user(
        "google_id",
        google_id,
        user_info.get("name", "Google User"),
        email=email,
    )
    if action == "linked":
        flash("Linked Google to your account! Welcome back!", "success")
    elif action == "created":
        flash("Welcome! Your Google account has been connected. 🎉", "success")

    login_user(UserWrapper(user_doc))
    return redirect(url_for("tracker.index"))
