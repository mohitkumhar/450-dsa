from bson import ObjectId
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import UserMixin, current_user, login_user, logout_user

from app.extensions import bcrypt, db, github, google, login_manager
from app.utils import utc_now


auth_bp = Blueprint("auth", __name__)


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
            return redirect(url_for("tracker.index"))
        flash("Login unsuccessful. Please check email and password.", "danger")
    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("tracker.index"))
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

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


@auth_bp.route("/login/github")
def login_github():
    redirect_uri = url_for("auth.authorize_github", _external=True)
    return github.authorize_redirect(redirect_uri)


@auth_bp.route("/login/github/authorize")
def authorize_github():
    token = github.authorize_access_token()
    if not token:
        return "GitHub authorization failed", 400

    response = github.get("user")
    if not response.ok:
        return "Failed to fetch GitHub user", 400

    user_info = response.json()
    github_id = str(user_info["id"])

    response_emails = github.get("user/emails")
    email = None
    if response_emails.status_code == 200:
        for email_item in response_emails.json():
            if email_item["primary"] and email_item["verified"]:
                email = email_item["email"]
                break

    user_doc = db.user.find_one({"github_id": github_id})
    if not user_doc:
        if email:
            user_doc = db.user.find_one({"email": email})
        if user_doc:
            db.user.update_one({"_id": user_doc["_id"]}, {"$set": {"github_id": github_id}})
            user_doc["github_id"] = github_id
        else:
            result = db.user.insert_one(
                {
                    "name": user_info.get("name", user_info.get("login", "GitHub User")),
                    "email": email,
                    "github_id": github_id,
                    "progress": {},
                    "is_admin": False,
                    "created_at": utc_now(),
                }
            )
            user_doc = db.user.find_one({"_id": result.inserted_id})

    login_user(UserWrapper(user_doc))
    return redirect(url_for("tracker.index"))


@auth_bp.route("/login/google")
def login_google():
    redirect_uri = url_for("auth.authorize_google", _external=True)
    return google.authorize_redirect(redirect_uri)


@auth_bp.route("/login/google/authorize")
def authorize_google():
    token = google.authorize_access_token()
    user_info = google.parse_id_token(token, nonce=session.get("nonce"))
    if not user_info:
        user_info = google.userinfo()

    google_id = user_info["sub"]
    email = user_info.get("email")

    user_doc = db.user.find_one({"google_id": google_id})
    if not user_doc:
        if email:
            user_doc = db.user.find_one({"email": email})
        if user_doc:
            db.user.update_one({"_id": user_doc["_id"]}, {"$set": {"google_id": google_id}})
            user_doc["google_id"] = google_id
        else:
            result = db.user.insert_one(
                {
                    "name": user_info.get("name", "Google User"),
                    "email": email,
                    "google_id": google_id,
                    "progress": {},
                    "is_admin": False,
                    "created_at": utc_now(),
                }
            )
            user_doc = db.user.find_one({"_id": result.inserted_id})

    login_user(UserWrapper(user_doc))
    return redirect(url_for("tracker.index"))
