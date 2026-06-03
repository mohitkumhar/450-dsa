from app.extensions import mongo
from datetime import datetime


def create_notification(user_id, notif_type, message):
    """Create a new notification for a user."""
    if mongo.db is None:
        return None
    mongo.db.notifications.insert_one({
        "user_id": user_id,
        "type": notif_type,
        "message": message,
        "read": False,
        "created_at": datetime.utcnow()
    })


def get_user_notifications(user_id, limit=20):
    """Get all notifications for a user, newest first."""
    if mongo.db is None:
        return []
    return list(mongo.db.notifications.find(
        {"user_id": user_id},
        {"_id": 1, "type": 1, "message": 1, "read": 1, "created_at": 1}
    ).sort("created_at", -1).limit(limit))


def get_unread_count(user_id):
    """Get count of unread notifications for a user."""
    if mongo.db is None:
        return 0
    return mongo.db.notifications.count_documents(
        {"user_id": user_id, "read": False}
    )


def mark_all_read(user_id):
    """Mark all notifications as read for a user."""
    if mongo.db is None:
        return
    mongo.db.notifications.update_many(
        {"user_id": user_id, "read": False},
        {"$set": {"read": True}}
    )


def mark_one_read(user_id, notification_id):
    """Mark a single notification as read."""
    if mongo.db is None:
        return
    from bson import ObjectId
    mongo.db.notifications.update_one(
        {"_id": ObjectId(notification_id), "user_id": user_id},
        {"$set": {"read": True}}
    )
