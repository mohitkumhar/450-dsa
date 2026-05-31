from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app.badges.models import get_user_badges

badges_bp = Blueprint("badges", __name__)


@badges_bp.route("/api/badges", methods=["GET"])
@login_required
def get_my_badges():
    """Return all badges earned by the current user."""
    badges = get_user_badges(current_user.id)
    return jsonify([
        {
            "key": b["badge_key"],
            "name": b["badge_name"],
            "earned_at": b["earned_at"].isoformat()
        }
        for b in badges
    ])
