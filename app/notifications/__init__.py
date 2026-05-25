from flask import Blueprint

notifications_bp = Blueprint("notifications", __name__)

from app.notifications import routes
