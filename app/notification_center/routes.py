from flask import jsonify, request
from flask_login import current_user, login_required
from app.extensions import db
from app.notification_center import notification_center_bp
from app.notification_center.models import (
    get_user_notifications, get_unread_count,
    mark_notification_read, mark_all_read, delete_notification,
)


@notification_center_bp.get("/")
@login_required
def get_notifications():
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    limit = min(int(request.args.get("limit", 20)), 50)
    notifications = get_user_notifications(db, str(current_user._id), limit=limit, unread_only=unread_only)
    unread_count = get_unread_count(db, str(current_user._id))
    return jsonify({"success": True, "notifications": notifications, "unread_count": unread_count})


@notification_center_bp.get("/unread-count")
@login_required
def unread_count():
    count = get_unread_count(db, str(current_user._id))
    return jsonify({"success": True, "unread_count": count})


@notification_center_bp.post("/mark-read/<notif_id>")
@login_required
def mark_read(notif_id):
    success = mark_notification_read(db, notif_id, str(current_user._id))
    count = get_unread_count(db, str(current_user._id))
    return jsonify({"success": success, "unread_count": count})


@notification_center_bp.post("/mark-all-read")
@login_required
def mark_all_read_route():
    count = mark_all_read(db, str(current_user._id))
    return jsonify({"success": True, "marked_count": count, "unread_count": 0})


@notification_center_bp.delete("/<notif_id>")
@login_required
def delete_notif(notif_id):
    success = delete_notification(db, notif_id, str(current_user._id))
    count = get_unread_count(db, str(current_user._id))
    return jsonify({"success": success, "unread_count": count})
