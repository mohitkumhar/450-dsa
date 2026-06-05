from datetime import datetime
from bson import ObjectId


def _get_db():
    import app.extensions as _ext
    return _ext.db


def init_notification_preferences(user_id):
    """Initialize notification preferences for a new user."""
    db = _get_db()
    if db is None:
        return None
    existing = db.notification_preferences.find_one({"user_id": ObjectId(user_id)})
    if existing:
        return existing
    prefs = {
        "user_id": ObjectId(user_id),
        "browser_notifications_enabled": False,
        "notification_types": {
            "due_goals": True,
            "reminders": True,
            "challenges": True,
        },
        "permission_status": "default",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = db.notification_preferences.insert_one(prefs)
    prefs["_id"] = result.inserted_id
    return prefs



def get_notification_preferences(user_id):
    """Get notification preferences for a user."""
    db = _get_db()
    if db is None:
        return None
    try:
        return db.notification_preferences.find_one({"user_id": ObjectId(user_id)})
    except AttributeError:
        return None

def update_notification_permission(user_id, permission_status):
    """Update browser notification permission status."""
    db = _get_db()
    result = db.notification_preferences.update_one(
        {"user_id": ObjectId(user_id)},
        {
            "$set": {
                "permission_status": permission_status,
                "browser_notifications_enabled": permission_status == "granted",
                "updated_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )
    return result.modified_count > 0 or result.upserted_id is not None


def update_notification_type(user_id, notification_type, enabled):
    """Enable/disable a specific notification type."""
    db = _get_db()
    result = db.notification_preferences.update_one(
        {"user_id": ObjectId(user_id)},
        {
            "$set": {
                f"notification_types.{notification_type}": enabled,
                "updated_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )
    return result.modified_count > 0 or result.upserted_id is not None


def should_send_notification(user_id, notification_type):
    """Check if a notification should be sent to user."""
    prefs = get_notification_preferences(user_id)
    if not prefs:
        return False
    return (
        prefs.get("browser_notifications_enabled", False)
        and prefs.get("notification_types", {}).get(notification_type, False)
    )