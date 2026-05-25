from flask import Blueprint
from app.notifications import routes

notifications_bp = Blueprint("notifications", __name__)

