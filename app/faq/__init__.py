from flask import Blueprint

faq_bp = Blueprint("faq", __name__)

from app.faq import routes as routes  # noqa: E402,F401