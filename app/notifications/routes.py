from flask import jsonify, request
from flask_login import current_user, login_required
from app.notifications import notifications_bp
from app.notifications.models import (
    init_notification_preferences,
    get_notification_preferences,
    update_notification_permission,
    update_notification_type,
)
from app.notifications.service import (
    check_review_reminders,
    check_goal_deadlines,
    check_challenge_deadlines,
)
from app.extensions import db
from bson import ObjectId


@notifications_bp.route("/notifications/init", methods=["POST"])
@login_required
def initialize_notifications():
    """Initialize notification preferences for user."""
    init_notification_preferences(current_user.id)
    return jsonify({"status": "success", "message": "Notifications initialized"})


@notifications_bp.route("/notifications/permission", methods=["POST"])
@login_required
def update_permission():
    """Update browser notification permission status."""
    data = request.get_json()
    permission_status = data.get("permission_status")  # granted, denied, default

    if permission_status not in ["granted", "denied", "default"]:
        return jsonify({"status": "error", "message": "Invalid permission status"}), 400

    success = update_notification_permission(current_user.id, permission_status)
    return jsonify({"status": "success" if success else "error"})


@notifications_bp.route("/notifications/preferences", methods=["GET"])
@login_required
def get_preferences():
    """Get current notification preferences."""
    prefs = get_notification_preferences(current_user.id)
    if not prefs:
        prefs = init_notification_preferences(current_user.id)

    # Remove MongoDB ObjectId from response
    prefs.pop("_id", None)
    return jsonify(prefs)


@notifications_bp.route("/notifications/preferences/<notification_type>", methods=["PUT"])
@login_required
def update_preference(notification_type):
    """Update a specific notification type preference."""
    valid_types = ["due_goals", "reminders", "challenges"]
    if notification_type not in valid_types:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Invalid notification type. Must be one of: {', '.join(valid_types)}",
                }
            ),
            400,
        )

    data = request.get_json()
    enabled = data.get("enabled", True)

    success = update_notification_type(current_user.id, notification_type, enabled)
    return jsonify({"status": "success" if success else "error"})


@notifications_bp.route("/notifications/subscribe", methods=["POST"])
@login_required
def subscribe():
    """Subscribe to browser notifications (legacy endpoint)."""
    update_notification_permission(current_user.id, "granted")
    return jsonify({"status": "success"})


@notifications_bp.route("/notifications/unsubscribe", methods=["POST"])
@login_required
def unsubscribe():
    """Unsubscribe from browser notifications (legacy endpoint)."""
    update_notification_permission(current_user.id, "denied")
    return jsonify({"status": "success"})


@notifications_bp.route("/notifications/check-reminders", methods=["POST"])
@login_required
def check_reminders():
    """Check and send review reminders for current user."""
    check_review_reminders(current_user.id)
    return jsonify({"status": "success", "message": "Reminders checked"})


@notifications_bp.route("/notifications/check-goals", methods=["POST"])
@login_required
def check_goals():
    """Check and send goal deadline notifications for current user."""
    check_goal_deadlines(current_user.id)
    return jsonify({"status": "success", "message": "Goal deadlines checked"})


@notifications_bp.route("/notifications/check-challenges", methods=["POST"])
@login_required
def check_challenges():
    """Check and send challenge deadline notifications for current user."""
    check_challenge_deadlines(current_user.id)
    return jsonify({"status": "success", "message": "Challenge deadlines checked"})


@notifications_bp.route("/notifications/check-all", methods=["POST"])
@login_required
def check_all():
    """Check all notification types for current user."""
    check_review_reminders(current_user.id)
    check_goal_deadlines(current_user.id)
    check_challenge_deadlines(current_user.id)
    return jsonify({"status": "success", "message": "All notifications checked"})
