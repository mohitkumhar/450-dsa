from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app.notifications.models import (
    get_user_notifications,
    get_unread_count,
    mark_all_read,
    mark_one_read
)

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/api/notifications", methods=["GET"])
@login_required
def get_notifications():
    """Return all notifications for the current user."""
    notifications = get_user_notifications(current_user.id)
    return jsonify([
        {
            "id": str(n["_id"]),
            "type": n["type"],
            "message": n["message"],
            "read": n["read"],
            "created_at": n["created_at"].isoformat()
        }
        for n in notifications
    ])


@notifications_bp.route("/api/notifications/unread-count", methods=["GET"])
@login_required
def unread_count():
    """Return count of unread notifications."""
    count = get_unread_count(current_user.id)
    return jsonify({"count": count})


@notifications_bp.route("/api/notifications/mark-all-read", methods=["POST"])
@login_required
def mark_all_as_read():
    """Mark all notifications as read."""
    mark_all_read(current_user.id)
    return jsonify({"success": True})


@notifications_bp.route(
    "/api/notifications/<notification_id>/read",
    methods=["POST"]
)
@login_required
def mark_as_read(notification_id):
    """Mark a single notification as read."""
    mark_one_read(current_user.id, notification_id)
    return jsonify({"success": True})
