from flask import Blueprint

notification_center_bp = Blueprint("notification_center", __name__, url_prefix="/notifications")

from app.notification_center import routes  # noqa: E402, F401